import pytest
from services.chat.evidence_gate import normalize_value, validate_verification, eligible_sources, citation_indices, literal_property_decision

def test_fabricated_quote_and_reference_are_rejected():
    sources=[{'document_id':'doc-a','visible_text':'The timeout is 60 seconds.'}]
    result={'status':'answerable','values':['60'],'citations':[1],'answer':'60 seconds [1].','evidence':[{'source':1,'quote':'The timeout is 90 seconds.'}]}
    with pytest.raises(ValueError,match='quotation_not'):validate_verification(result,sources)
    result['evidence'][0]['quote']='The timeout is 60 seconds.'
    checked=validate_verification(result,sources)
    assert checked['evidence'][0]['char_end']==26
    result['answer']='60 seconds [2].'
    with pytest.raises(ValueError,match='reference_not_declared'):validate_verification(result,sources)

def test_abstention_cannot_hide_a_positive_claim():
    with pytest.raises(ValueError,match='positive_claims'):
        validate_verification({'status':'insufficient','values':['60'],'citations':[],'evidence':[]},[])

def test_dispute_requires_at_least_two_alternatives():
    source=[{'document_id':'d','visible_text':'The timeout is 60 seconds.'}]
    with pytest.raises(ValueError,match='without_alternatives'):
        validate_verification({'status':'disputed','values':['60'],'citations':[1],'answer':'Unresolved [1].','evidence':[{'source':1,'quote':'The timeout is 60 seconds.'}]},source)

def test_unit_normalization_preserves_identifiers_and_dates():
    assert normalize_value('60,000 milliseconds')=='60'
    assert normalize_value('60 seconds')=='60'
    assert normalize_value('INR 690000')=='690000'
    assert normalize_value('2026-10-10')=='2026-10-10'
    assert normalize_value('45 days [1, 5]')=='45'

def test_explicit_validity_governs_instead_of_publication_order():
    sources=[{'visible_text':'Project: Example\nPublished: 2026-10-12\nValid from: 2026-09-01\nValid through: 2026-09-30\n\nPast policy.'},
             {'visible_text':'Project: Example\nPublished: 2026-10-02\nValid from: 2026-10-01\nValid through: open\n\nCurrent policy.'}]
    assert eligible_sources('For Example, what is the policy as of 2026-10-14?',sources)[0]=={2}
    assert eligible_sources('For Example, what is the policy as of 2026-09-15?',sources)[0]=={1}

def test_drafts_are_excluded_only_with_an_explicit_governance_rule():
    sources=[{'visible_text':'Project: Example\nApproval status: draft\n\nProposed value.'}]
    assert eligible_sources('For Example, what is the value?',sources)[0]=={1}
    sources.append({'visible_text':'Project: Example\n\nGovernance rule: draft proposals do not replace an approved register.'})
    assert eligible_sources('For Example, what is the value?',sources)[0]=={2}

def test_quoted_sentence_does_not_validate_a_different_value():
    result={'status':'answerable','values':['90'],'citations':[1],'answer':'90 seconds [1].','evidence':[{'source':1,'quote':'The timeout is 60 seconds.'}]}
    with pytest.raises(ValueError,match='value_absent'):
        validate_verification(result,[{'document_id':'d','visible_text':'The timeout is 60 seconds.'}])

def test_grouped_citations_are_counted_as_used_references():
    assert citation_indices('Current [1, 6]; earlier [2].')=={1,2,6}

def test_literal_scalar_conflict_preserves_both_approved_values():
    sources=[{'visible_text':f'Project: Atlas\nScope: global\nApproval status: approved\n\nThe spending limit for Atlas is INR {value}.'} for value in ('1100','2200','1100')]
    result=literal_property_decision('For Atlas, what is the spending limit in INR?',sources)
    assert result['status']=='disputed'
    assert set(result['values'])=={'1100','2200'}
    assert len(result['evidence'])==2
    sources[1]['visible_text']=sources[1]['visible_text'].replace('approved','draft')
    assert literal_property_decision('For Atlas, what is the spending limit in INR?',sources) is None

def test_literal_parser_does_not_replace_a_relational_question_with_owner():
    sources=[{'visible_text':'Project: Atlas\nScope: global\nApproval status: approved\n\nThe responsible owner for Atlas is Ada.'}]
    assert literal_property_decision('Which team does the responsible owner of Atlas belong to?',sources) is None

def test_conflict_counts_include_failed_positive_questions():
    from scripts.grade_application import disputed_confusion
    result=disputed_confusion([
        {'expected_status':'disputed','predicted_status':'disputed','error':None},
        {'expected_status':'disputed','predicted_status':'disputed','error':'provider failure'},
        {'expected_status':'disputed','predicted_status':'answerable','error':None},
        {'expected_status':'answerable','predicted_status':'disputed','error':None},
        {'expected_status':'insufficient','predicted_status':'insufficient','error':None},
    ])
    assert result=={'tp':1,'fp':1,'fn':2,'tn':1}
