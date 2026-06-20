import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { recommendationRunId: string } }
) {
  try {
    const { recommendationRunId } = params;
    const url = `${BACKEND_URL}/api/recommendations/${recommendationRunId}/risk-reviews`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        // Forward auth headers if present
        ...(request.headers.get('authorization') && { 'Authorization': request.headers.get('authorization')! }),
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch risk reviews', status: response.status },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching risk reviews:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: { recommendationRunId: string } }
) {
  try {
    const { recommendationRunId } = params;
    const body = await request.json();
    const url = `${BACKEND_URL}/api/recommendations/${recommendationRunId}/risk-reviews`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(request.headers.get('authorization') && { 'Authorization': request.headers.get('authorization')! }),
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to submit risk review', status: response.status },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, { status: 201 });
  } catch (error) {
    console.error('Error submitting risk review:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
