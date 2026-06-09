// ── Recommendation Completeness Score ─────────────────────────────────────────────

export interface CompletenessScoreInput {
  impactedAreasCount: number;
  areasWithDirectTests: number;
  areasWithSuggestedScenarios: number;
  coverageConfidence: "HIGH" | "MODERATE" | "LOW";
  evidenceGaps: { severity: string; message: string }[];
  missingScenarioCount: number;
  totalRecommendedTests: number;
}

export interface CompletenessScoreOutput {
  level: "LOW" | "PARTIAL" | "GOOD";
  score: number; // 0-100
  explanation: string;
  improvementSuggestions: string[];
}

export function calculateCompletenessScore(input: CompletenessScoreInput): CompletenessScoreOutput {
  const {
    impactedAreasCount,
    areasWithDirectTests,
    areasWithSuggestedScenarios,
    coverageConfidence,
    evidenceGaps,
    missingScenarioCount,
    totalRecommendedTests
  } = input;

  // Calculate base coverage score with division by zero protection
  const directTestCoverage = (impactedAreasCount > 0 && areasWithDirectTests >= 0)
    ? (areasWithDirectTests / impactedAreasCount) * 100
    : 0;

  const suggestedScenarioCoverage = (impactedAreasCount > 0 && areasWithSuggestedScenarios >= 0)
    ? (areasWithSuggestedScenarios / impactedAreasCount) * 100
    : 0;

  // Confidence weight
  const confidenceWeight = coverageConfidence === "HIGH" ? 1.0 : 
                          coverageConfidence === "MODERATE" ? 0.7 : 0.4;

  // Evidence gaps penalty
  const highSeverityGaps = evidenceGaps.filter(g => g.severity === "HIGH").length;
  const gapsPenalty = highSeverityGaps * 15;

  // Calculate overall score
  let score = (directTestCoverage * 0.6 + suggestedScenarioCoverage * 0.4) * confidenceWeight;
  score = Math.max(0, score - gapsPenalty);
  score = Math.min(100, score);

  // Determine level
  let level: "LOW" | "PARTIAL" | "GOOD";
  if (score >= 70) {
    level = "GOOD";
  } else if (score >= 40) {
    level = "PARTIAL";
  } else {
    level = "LOW";
  }

  // Generate explanation
  const explanation = generateExplanation({
    level,
    directTestCoverage,
    suggestedScenarioCoverage,
    coverageConfidence,
    totalRecommendedTests,
    missingScenarioCount,
    highSeverityGaps,
    impactedAreasCount
  });

  // Generate improvement suggestions
  const improvementSuggestions = generateImprovementSuggestions({
    level,
    coverageConfidence,
    highSeverityGaps,
    missingScenarioCount,
    directTestCoverage,
    suggestedScenarioCoverage
  });

  return {
    level,
    score: Math.round(score),
    explanation,
    improvementSuggestions
  };
}

function generateExplanation(params: {
  level: "LOW" | "PARTIAL" | "GOOD";
  directTestCoverage: number;
  suggestedScenarioCoverage: number;
  coverageConfidence: string;
  totalRecommendedTests: number;
  missingScenarioCount: number;
  highSeverityGaps: number;
  impactedAreasCount: number;
}): string {
  const {
    level,
    directTestCoverage,
    suggestedScenarioCoverage,
    coverageConfidence,
    totalRecommendedTests,
    missingScenarioCount,
    highSeverityGaps,
    impactedAreasCount
  } = params;

  if (level === "GOOD") {
    return `Good: ${totalRecommendedTests} existing tests are recommended with ${coverageConfidence.toLowerCase()} confidence. ${Math.round(directTestCoverage)}% of impacted areas have direct test coverage. ${missingScenarioCount > 0 ? `${missingScenarioCount} scenarios are suggested for additional edge case coverage.` : 'All critical flows are covered.'}`;
  }

  if (level === "PARTIAL") {
    let explanation = `Partial: ${totalRecommendedTests} existing tests are recommended, but `;
    
    if (directTestCoverage < 50) {
      explanation += `${Math.round(100 - directTestCoverage)}% of impacted flows still require suggested scenarios because direct automation coverage is missing. `;
    } else {
      explanation += `${missingScenarioCount} additional scenarios are suggested to improve coverage. `;
    }
    
    if (coverageConfidence === "LOW") {
      explanation += `Coverage confidence is ${coverageConfidence.toLowerCase()} due to limited evidence. `;
    }
    
    if (highSeverityGaps > 0) {
      explanation += `${highSeverityGaps} high-severity evidence gaps exist. `;
    }
    
    return explanation.trim();
  }

  // LOW
  let explanation = `Low: Only ${totalRecommendedTests} existing tests are recommended with ${coverageConfidence.toLowerCase()} confidence. `;
  
  if (directTestCoverage < 30) {
    explanation += `Direct test coverage is limited to ${Math.round(directTestCoverage)}% of ${impactedAreasCount} impacted areas. `;
  }
  
  if (missingScenarioCount > 5) {
    explanation += `${missingScenarioCount} scenarios are suggested to address missing coverage. `;
  }
  
  if (highSeverityGaps > 0) {
    explanation += `${highSeverityGaps} high-severity evidence gaps limit recommendation quality. `;
  }
  
  return explanation.trim();
}

function generateImprovementSuggestions(params: {
  level: "LOW" | "PARTIAL" | "GOOD";
  coverageConfidence: string;
  highSeverityGaps: number;
  missingScenarioCount: number;
  directTestCoverage: number;
  suggestedScenarioCoverage: number;
}): string[] {
  const suggestions: string[] = [];

  if (params.coverageConfidence === "LOW") {
    suggestions.push("Improve evidence quality by running existing test suite to gather coverage data");
  }

  if (params.highSeverityGaps > 0) {
    suggestions.push("Address high-severity evidence gaps by adding historical test data or coverage reports");
  }

  if (params.directTestCoverage < 50) {
    suggestions.push("Increase direct test coverage by adding automated tests for core impacted flows");
  }

  if (params.missingScenarioCount > 5) {
    suggestions.push("Implement suggested test scenarios to improve overall coverage");
  }

  if (params.suggestedScenarioCoverage > 70 && params.directTestCoverage < 30) {
    suggestions.push("Convert suggested scenarios into automated tests to improve direct coverage");
  }

  if (suggestions.length === 0) {
    suggestions.push("Continue monitoring and refine recommendations as more evidence becomes available");
  }

  return suggestions;
}
