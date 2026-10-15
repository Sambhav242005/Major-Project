"""Headless evaluation of existing ingestion/embedding/graph components.

Run from the repository root with the isolated research virtual environment.
Only raw source files and whitelisted questions are used during inference.
Gold annotations are read only by the separate scoring command.
"""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0,str(API))
from core.config import settings

WORK = ROOT/'output/research_benchmark/application'
WORK.mkdir(parents=True,exist_ok=True)
# Process-local settings only. Never change the user's .env or original stores.
settings.DATABASE_URL='sqlite+aiosqlite:///'+(WORK/'evaluation.sqlite').as_posix()
settings.CHROMA_PATH=str(WORK/'chroma')
settings.LLM_BASE_URL='http://127.0.0.1:11434/v1'
settings.LLM_API_KEY=''
settings.LLM_CHAT_MODEL=settings.LLM_EXTRACT_MODEL='akgb-qwen2.5-7b'
settings.EMBEDDING_PROVIDER='openai'
settings.EMBEDDING_BASE_URL=settings.LLM_BASE_URL
settings.EMBEDDING_API_KEY=''
settings.EMBEDDING_MODEL='nomic-embed-text:v1.5'
settings.EMBEDDING_OUTPUT_DIM=None
settings.MOCK_AUTH=True

from sqlalchemy import select,func
from db.session import Base,_get_engine,async_session_factory
from db.models import Document,DocumentChunk,Entity,EntityMention,Relationship,Profile,Project,ProjectMember
from pipelines.ingestion.pipeline import _ingest_document_body
from pipelines.embeddings.query import query_chunks
from services.chat.retrieval import _get_entity_context,_expand_via_graph,_format_source_block
from services.chat.prompt import build_entity_context,build_user_prompt,build_messages
from services.chat.evidence_gate import verify_answer,response_schema,citation_indices
from pipelines import llm_client
import httpx

DATA = ROOT/'output/research_benchmark/akgb_synthetic_v1'
NAMESPACE=uuid.UUID('c5633a9c-3994-467b-9d96-86875c7eb804')
OWNER=uuid.uuid5(NAMESPACE,'research-owner')
FORMAT='''\nReturn a JSON answer following the supplied schema. status is answerable,
disputed, or insufficient. values contains the requested short answer as strings;
numeric answers use requested units without suffixes. answer MUST contain complete
sentences giving those values and bracket citations [n]. A bare reference is not
an answer. For insufficient use empty values/citations and explain the missing
information in answer. citations lists only the numbered sources actually used.
Answer the question asked, including team or office rather than just owner when
those are requested. Include all alternatives if the answer is disputed.'''
USAGES=[]

async def capture_usage(response):
    if response.request.url.path.endswith('/chat/completions') and not json.loads(response.request.content).get('stream'):
        await response.aread()
        if response.status_code==200:
            data=response.json()
            USAGES.append({'usage':data.get('usage',{}),'finish_reason':data['choices'][0].get('finish_reason')})


def project_id(split):return uuid.uuid5(NAMESPACE,split)
def write_json(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def emit(value):print(json.dumps(value),flush=True)


async def setup():
    llm_client._http_client=httpx.AsyncClient(timeout=120,event_hooks={'response':[capture_usage]})
    async with _get_engine().begin() as connection:await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        if not await db.get(Profile,OWNER):db.add(Profile(id=OWNER,full_name='Isolated benchmark runner'))
        await db.flush()
        for split in ('dev','test'):
            pid=project_id(split)
            if not await db.get(Project,pid):
                db.add(Project(id=pid,name='AKGB research '+split,owner_id=OWNER));await db.flush()
                db.add(ProjectMember(project_id=pid,user_id=OWNER,role='owner'))
        await db.commit()


async def ingest(split):
    paths=sorted((DATA/'raw'/split).glob('*.txt'))
    rows=[]
    log_path=WORK/f'ingestion_{split}.jsonl'
    previous={r['source_id']:r for r in map(json.loads,log_path.read_text().splitlines())} if log_path.exists() else {}
    async with async_session_factory() as db:
        for i,path in enumerate(paths,1):
            did=uuid.uuid5(NAMESPACE,split+'/'+path.name)
            existing=await db.get(Document,did)
            if existing and existing.status=='processed' and path.stem in previous:
                rows.append(previous[path.stem]);continue
            if existing:raise RuntimeError('Incomplete existing ingestion requires diagnosis, not silent re-ingestion: '+path.name)
            doc=Document(id=did,project_id=project_id(split),uploaded_by=OWNER,filename=path.name,file_type='text/plain',storage_path=str(path),status='pending')
            db.add(doc);await db.commit()
            start=time.perf_counter();u0=len(USAGES)
            await _ingest_document_body(db,str(did),path.read_bytes())
            await db.refresh(doc)
            chunks=(await db.execute(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id==did))).scalar_one()
            mentions=(await db.execute(select(func.count()).select_from(EntityMention).where(EntityMention.document_id==did))).scalar_one()
            edges=(await db.execute(select(func.count()).select_from(Relationship).where(Relationship.source_document_id==did))).scalar_one()
            row={'source_id':path.stem,'document_id':str(did),'source_sha256':digest(path),'split':split,'status':doc.status,'error':doc.error_message,'chunks':chunks,'mentions':mentions,'persisted_relationships':edges,'wall_seconds':time.perf_counter()-start,'llm_usage':USAGES[u0:]}
            rows.append(row)
            with log_path.open('a',encoding='utf-8') as out:out.write(json.dumps(row)+'\n')
            emit({'stage':'ingest','split':split,'progress':f'{i}/{len(paths)}',**row})
    write_json(WORK/f'ingestion_{split}_summary.json',{'documents':len(paths),'processed':sum(r['status']=='processed' for r in rows),'chunks':sum(r['chunks'] for r in rows),'documents_with_mentions':sum(r['mentions']>0 for r in rows),'documents_with_relationships':sum(r['persisted_relationships']>0 for r in rows),'total_wall_seconds':sum(r['wall_seconds'] for r in rows),'model':settings.LLM_EXTRACT_MODEL,'embedding':settings.EMBEDDING_MODEL})


async def run(split,limit):
    # Whitelist at the boundary. The model receives no family/category/gold fields.
    questions=[{k:q[k] for k in ('question_id','question','split')} for q in map(json.loads,(DATA/'private/questions.jsonl').read_text().splitlines()) if q['split']==split]
    if limit:questions=questions[:limit]
    if split=='test':
        if not (WORK/'experiment_freeze.json').exists():raise RuntimeError('Freeze development protocol before test inference')
        frozen=json.loads((WORK/'experiment_freeze.json').read_text())
        import research_benchmark
        if research_benchmark.dataset_content_digest(DATA)!=frozen['dataset_content_digest']:raise RuntimeError('Frozen dataset changed')
        for relative,expected in frozen['code_sha256'].items():
            if digest(ROOT/relative)!=expected:raise RuntimeError('Frozen experiment code changed: '+relative)
    files={name:WORK/f'{split}_{name}.jsonl' for name in ('A_vector','B_graph','C_verified')}
    completed={name:{r['question_id']:r for r in map(json.loads,p.read_text().splitlines())} if p.exists() else {} for name,p in files.items()}
    async with async_session_factory() as db:
        for i,q in enumerate(questions,1):
            if all(q['question_id'] in c for c in completed.values()):continue
            start=time.perf_counter()
            retrieved=await query_chunks(q['question'],str(project_id(split)),8,db)
            retrieval_wall=time.perf_counter()-start
            for r in retrieved:r['visible_text']=r['text'][:800]
            start=time.perf_counter()
            entities=await _get_entity_context(db,str(project_id(split)),[r['chunk_id'] for r in retrieved])
            expanded=await _expand_via_graph(db,str(project_id(split)),[e['id'] for e in entities],1)
            graph_wall=time.perf_counter()-start
            graph_context=build_entity_context(entities,expanded)
            sources='\n\n---\n\n'.join(_format_source_block(n,r['text'],r['filename'],r['page_number'],r['document_id']) for n,r in enumerate(retrieved,1))
            base={'question_id':q['question_id'],'question':q['question'],'split':split,'retrieved_doc_ids':[Path(r['filename']).stem for r in retrieved],'sources':retrieved,'retrieval_wall_seconds':retrieval_wall,'graph_wall_seconds':graph_wall,'graph_entities':entities,'graph_neighbors':expanded,'model':settings.LLM_CHAT_MODEL,'embedding':settings.EMBEDDING_MODEL}
            for name in ('A_vector','B_graph','C_verified'):
                if q['question_id'] in completed[name]:continue
                row={**base,'configuration':name};u0=len(USAGES);start=time.perf_counter()
                try:
                    if name=='C_verified':
                        candidate=completed['B_graph'][q['question_id']]
                        if candidate.get('error'):raise RuntimeError('Candidate generation failed')
                        prediction=await verify_answer(q['question'],candidate['prediction'],retrieved,llm_client.chat_completion,settings.LLM_CHAT_MODEL)
                        row['candidate_question_id']=candidate['question_id']
                        row['verification_wall_seconds']=time.perf_counter()-start
                        row['wall_seconds']=candidate['wall_seconds']+row['verification_wall_seconds']
                        row['llm_calls']=2
                        row['candidate_usage']=candidate['llm_usage']
                    else:
                        prompt=build_user_prompt(sources,graph_context if name=='B_graph' else '','',q['question'])+FORMAT
                        messages=build_messages(prompt)
                        row['prompt_messages']=messages
                        raw=await llm_client.chat_completion(messages,model=settings.LLM_CHAT_MODEL,temperature=0,response_format=response_schema(),max_tokens=1800)
                        row['raw_response']=raw;prediction=json.loads(raw)
                        if not isinstance(prediction.get('values'),list) or prediction.get('status') not in ('answerable','disputed','insufficient'):raise ValueError('Malformed structured answer')
                        row['wall_seconds']=retrieval_wall+(graph_wall if name=='B_graph' else 0)+time.perf_counter()-start
                        row['llm_calls']=1
                    row['prediction']=prediction
                    numbers=citation_indices(prediction.get('answer',''))
                    row['used_citation_indices']=sorted(numbers)
                    row['cited_doc_ids']=[Path(retrieved[n-1]['filename']).stem for n in sorted(numbers) if 1<=n<=len(retrieved)]
                    row['invalid_citations']=[n for n in numbers if not 1<=n<=len(retrieved)]
                    row['declared_but_unused_citations']=sorted(set(prediction.get('citations',[]))-numbers)
                    row['error']=None
                except Exception as exc:
                    row['error']=f'{type(exc).__name__}: {exc}'
                    if hasattr(exc,'raw_response'):row['verifier_raw_response']=exc.raw_response
                    row['prediction']={};row['cited_doc_ids']=[]
                    row['wall_seconds']=retrieval_wall+time.perf_counter()-start
                    if name=='C_verified' and q['question_id'] in completed['B_graph']:row['wall_seconds']+=completed['B_graph'][q['question_id']]['wall_seconds']
                row['llm_usage']=USAGES[u0:]
                with files[name].open('a',encoding='utf-8') as out:out.write(json.dumps(row)+'\n')
                completed[name][q['question_id']]=row
                emit({'stage':'answer','split':split,'progress':f'{i}/{len(questions)}','question_id':q['question_id'],'configuration':name,'error':row['error'],'seconds':round(row['wall_seconds'],2),'prediction':row['prediction']})


def freeze():
    for name in ('A_vector','B_graph','C_verified'):
        path=WORK/f'dev_{name}.jsonl'
        if not path.exists() or len(path.read_text().splitlines())!=30:raise RuntimeError('Complete all development pilot outputs before freezing')
    import research_benchmark
    if research_benchmark.review_status(DATA)!='first_pass_accepted':raise RuntimeError('Dataset review is not valid')
    value={'frozen_utc':datetime.now(timezone.utc).isoformat(),'dataset_content_digest':research_benchmark.dataset_content_digest(DATA),'top_k':8,'source_character_limit':800,'chunk_tokens':600,'overlap_tokens':80,'model':settings.LLM_CHAT_MODEL,'embedding':settings.EMBEDDING_MODEL,'temperature':0,'seed':26014,'context_tokens':8192,'max_output_tokens':1800,'comparison':'A vector; B existing graph descriptions; C reuses B candidate and adds one verification call','no_training':True,'no_persistent_graph_repair':True,'review':'one human source/gold reviewer plus non-blind AI source sample; generated answer grading is AI-assisted','code_sha256':{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),API/'services/chat/evidence_gate.py',API/'scripts/research_benchmark.py',API/'scripts/grade_application.py',API/'services/audit.py',API/'services/chat/prompt.py',API/'services/chat/retrieval.py',API/'pipelines/extraction/pipeline.py']},'settings':{'database':settings.DATABASE_URL,'chroma_path':settings.CHROMA_PATH,'llm_endpoint':settings.LLM_BASE_URL},'versions':{p:importlib.metadata.version(p) for p in ('chromadb','SQLAlchemy','spacy','httpx','tiktoken','pydantic-settings')}}
    write_json(WORK/'experiment_freeze.json',value)
    receipt_path=DATA/'private/review_acceptance.json';receipt=json.loads(receipt_path.read_text());receipt['experiment_freeze_status']='frozen';write_json(receipt_path,receipt)
    emit(value)


async def pilot():
    from services.chat.sessions import create_session,get_session
    from services.chat.streaming import send_message
    from core.security import User
    async with async_session_factory() as db:
        session=await create_session(db,User(id=str(OWNER)),str(project_id('dev')),'Research application service pilot')
        events=[];start=time.perf_counter()
        async for event in send_message(db,session['id'],'Which team does the responsible owner of Aster-543783 belong to?',str(project_id('dev')),OWNER):events.append(event)
        await db.commit()
        persisted=await get_session(db,session['id'],str(project_id('dev')))
        answer=''.join(e.get('content','') for e in events if e.get('type')=='chunk')
        successful=bool(answer) and not any(e.get('type')=='error' for e in events) and 'encountered an error' not in answer
        result={'execution':'in-process existing application chat service, no HTTP listener or frontend launched','successful':successful,'answer':answer,'wall_seconds':time.perf_counter()-start,'events':events,'persisted_session':persisted,'model':settings.LLM_CHAT_MODEL,'embedding':settings.EMBEDDING_MODEL,'limitations':['Frontend, HTTP route transport and production authentication were not exercised.']}
        write_json(WORK/'application_service_pilot.json',result);emit(result)
        if not successful:raise RuntimeError('Application pilot failed')


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['ingest','run','freeze','pilot']);parser.add_argument('--split',choices=['dev','test'],default='dev');parser.add_argument('--limit',type=int,default=0);args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    await setup()
    try:
        if args.action=='ingest':await ingest(args.split)
        elif args.action=='run':await run(args.split,args.limit)
        elif args.action=='pilot':await pilot()
        else:freeze()
    finally:
        await llm_client._http_client.aclose();await _get_engine().dispose()

if __name__=='__main__':asyncio.run(main())
