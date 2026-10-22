import { NextResponse } from "next/server";

// Demo authentication has been retired. Never issue mock session cookies.
export async function GET() {
  return NextResponse.json({ error: "Demo authentication is unavailable. Create an account or sign in." }, { status: 404 });
}

export const POST = GET;
