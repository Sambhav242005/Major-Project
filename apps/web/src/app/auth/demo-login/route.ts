import { NextResponse, type NextRequest } from "next/server";

function createDemoResponse(request: NextRequest) {
  const response = NextResponse.redirect(new URL("/dashboard", request.nextUrl.origin));

  // Set mock session cookie for demo user
  response.cookies.set("mock-session", "demo-user-001", {
    path: "/",
    maxAge: 3600,
    httpOnly: false,
  });

  return response;
}

// GET allows page.goto() in E2E tests
export async function GET(request: NextRequest) {
  return createDemoResponse(request);
}

// POST allows form submissions from landing/signin pages
export async function POST(request: NextRequest) {
  return createDemoResponse(request);
}
