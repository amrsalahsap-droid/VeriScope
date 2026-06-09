import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle } from 'lucide-react';

export interface MissingIntelligenceItem {
  id: string;
  name: string;
  description: string;
  impact: string;
  confidenceImpact: number;
}

export function createMissingIntelligenceItems(businessIntent: any, requirementContext: any, manualTests: any, testHistory: any): MissingIntelligenceItem[] {
  const items: MissingIntelligenceItem[] = [];
  if (!businessIntent?.has_business_intent) {
    items.push({ id: 'ac', name: 'Acceptance Criteria', description: 'No AC defined', impact: 'Reduced precision', confidenceImpact: 12 });
  }
  if (!requirementContext?.linked_work_items?.length) {
    items.push({ id: 'work-items', name: 'Linked Work Items', description: 'No work items linked', impact: 'Limited traceability', confidenceImpact: 8 });
  }
  if (!manualTests?.length) {
    items.push({ id: 'manual-tests', name: 'Manual Tests', description: 'No manual tests', impact: 'Reduced coverage', confidenceImpact: 5 });
  }
  if (!testHistory?.has_flakiness_data) {
    items.push({ id: 'test-history', name: 'Test History', description: 'No test history', impact: 'Limited insights', confidenceImpact: 10 });
  }
  return items;
}

export default function MissingIntelligence({ missingSignals = [] }: { missingSignals: MissingIntelligenceItem[] }) {
  if (!missingSignals.length) return null;
  const totalImpact = missingSignals.reduce((sum, item) => sum + item.confidenceImpact, 0);
  return (
    <Card className="bg-zinc-800/40 border border-zinc-700/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-medium text-zinc-100 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          Missing Intelligence
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-zinc-400">Missing Signals</span>
          <span className="text-amber-400">{missingSignals.length}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-zinc-400">Confidence Impact</span>
          <span className="text-rose-400">-{totalImpact}%</span>
        </div>
        {missingSignals.map((item) => (
          <div key={item.id} className="bg-zinc-900/50 border border-zinc-700/50 rounded p-2">
            <div className="flex justify-between">
              <span className="text-sm text-zinc-200">{item.name}</span>
              <Badge variant="outline" className="text-xs text-rose-400">-{item.confidenceImpact}%</Badge>
            </div>
            <p className="text-xs text-zinc-400 mt-1">{item.description}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}