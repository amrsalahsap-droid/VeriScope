// ── Test Deduplication Logic ─────────────────────────────────────────────

interface TestItem {
  id: string;
  stable_identity?: string;
  title: string;
  type: 'existing' | 'missing' | 'optional' | 'excluded';
  tier?: 'must_run' | 'should_run' | 'fallback';
  requirement_id?: string;
  scenario_intent?: string;
}

/**
 * Deduplicates tests across sections using normalized title + requirement id + scenario intent
 * Priority order: Run Existing Tests > Create Missing Tests > Optional Tests > Excluded
 */
export function deduplicateTests(items: TestItem[]): TestItem[] {
  const priorityOrder: Record<TestItem['type'], number> = {
    existing: 0,
    missing: 1,
    optional: 2,
    excluded: 3
  };

  const itemMap = new Map<string, TestItem>();
  const duplicatesRemoved: string[] = [];

  items.forEach(item => {
    // Create normalized key
    const normalizedTitle = normalizeTitle(item.title);
    const key = `${normalizedTitle}|${item.requirement_id || ''}|${item.scenario_intent || ''}`;
    
    const existing = itemMap.get(key);
    
    if (!existing) {
      itemMap.set(key, item);
    } else {
      // Keep the item with higher priority (lower number = higher priority)
      if (priorityOrder[item.type] < priorityOrder[existing.type]) {
        if (process.env.NODE_ENV === 'development') {
          duplicatesRemoved.push(`Replaced ${existing.type} with ${item.type}: ${item.title}`);
        }
        itemMap.set(key, item);
      } else if (priorityOrder[item.type] === priorityOrder[existing.type]) {
        // Same priority - log duplicate in dev
        if (process.env.NODE_ENV === 'development') {
          console.warn(`Duplicate test detected (same priority): ${item.title}`);
        }
      } else {
        if (process.env.NODE_ENV === 'development') {
          duplicatesRemoved.push(`Skipped ${item.type} (kept ${existing.type}): ${item.title}`);
        }
      }
    }
  });

  if (process.env.NODE_ENV === 'development' && duplicatesRemoved.length > 0) {
    console.log('Test deduplication results:', duplicatesRemoved);
  }

  return Array.from(itemMap.values());
}

/**
 * Normalizes title for comparison
 */
function normalizeTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Groups tests by type for rendering
 */
export function groupTestsByType(tests: TestItem[]): {
  existing: TestItem[];
  missing: TestItem[];
  optional: TestItem[];
  excluded: TestItem[];
} {
  return {
    existing: tests.filter(t => t.type === 'existing'),
    missing: tests.filter(t => t.type === 'missing'),
    optional: tests.filter(t => t.type === 'optional'),
    excluded: tests.filter(t => t.type === 'excluded')
  };
}
