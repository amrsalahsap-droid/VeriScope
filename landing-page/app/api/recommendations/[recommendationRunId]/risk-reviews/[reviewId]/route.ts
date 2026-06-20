import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function DELETE(
  request: NextRequest,
  { params }: { params: { recommendationRunId: string; reviewId: string } }
) {
  try {
    const { recommendationRunId, reviewId } = params;
    const { searchParams } = new URL(request.url);
    const snapshotHash = searchParams.get('snapshotHash');
    
    const url = new URL(`${BACKEND_URL}/api/recommendations/${recommendationRunId}/risk-reviews/${reviewId}`);
    if (snapshotHash) {
      url.searchParams.set('snapshotHash', snapshotHash);
    }
    
    const response = await fetch(url.toString(), {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...(request.headers.get('authorization') && { 'Authorization': request.headers.get('authorization')! }),
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to delete risk review', status: response.status },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting risk review:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
