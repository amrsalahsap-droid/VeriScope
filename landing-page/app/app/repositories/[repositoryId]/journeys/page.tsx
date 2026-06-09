"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, AlertTriangle, CheckCircle, Clock, ChevronDown, ChevronUp } from "lucide-react";

interface JourneyHealth {
  id: string;
  name: string;
  slug: string;
  risk_level: string;
  coverage_score: number;
  behavior_count: number;
  testing_health: string;
  status: string;
  description: string;
  business_value: string;
}

interface JourneyDetails {
  behaviors: Array<{
    name: string;
    risk_level: string;
    coverage: number;
  }>;
  coverage: {
    covered: string[];
    partially_covered: string[];
    uncovered: string[];
  };
  scenarios: number;
  risks: string[];
}

export default function JourneysPage() {
  const params = useParams();
  const router = useRouter();
  const repositoryId = params.repositoryId as string;

  const [journeys, setJourneys] = useState<JourneyHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedJourney, setExpandedJourney] = useState<string | null>(null);
  const [journeyDetails, setJourneyDetails] = useState<Record<string, JourneyDetails>>({});

  useEffect(() => {
    fetchJourneys();
  }, [repositoryId]);

  const fetchJourneys = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/repositories/${repositoryId}/journeys/health`);
      if (!response.ok) {
        throw new Error("Failed to fetch journeys");
      }
      const data = await response.json();
      setJourneys(data.journeys || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load journeys");
    } finally {
      setLoading(false);
    }
  };

  const fetchJourneyDetails = async (journeyId: string) => {
    try {
      const response = await fetch(`/api/repositories/${repositoryId}/journeys/${journeyId}/details`);
      if (!response.ok) {
        throw new Error("Failed to fetch journey details");
      }
      const data = await response.json();
      setJourneyDetails((prev) => ({
        ...prev,
        [journeyId]: data,
      }));
    } catch (err) {
      console.error("Failed to fetch journey details:", err);
    }
  };

  const toggleExpand = (journeyId: string) => {
    if (expandedJourney === journeyId) {
      setExpandedJourney(null);
    } else {
      setExpandedJourney(journeyId);
      if (!journeyDetails[journeyId]) {
        fetchJourneyDetails(journeyId);
      }
    }
  };

  const getRiskBadge = (riskLevel: string) => {
    const colors = {
      CRITICAL: "bg-red-100 text-red-800 border-red-200",
      HIGH: "bg-orange-100 text-orange-800 border-orange-200",
      MEDIUM: "bg-yellow-100 text-yellow-800 border-yellow-200",
      LOW: "bg-green-100 text-green-800 border-green-200",
    };
    const color = colors[riskLevel as keyof typeof colors] || colors.MEDIUM;
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${color}`}>
        {riskLevel}
      </span>
    );
  };

  const getCoverageColor = (score: number) => {
    if (score >= 80) return "text-green-600";
    if (score >= 50) return "text-yellow-600";
    return "text-red-600";
  };

  const getTestingHealthIcon = (health: string) => {
    if (health === "HEALTHY") return <CheckCircle className="w-4 h-4 text-green-600" />;
    if (health === "WARNING") return <Clock className="w-4 h-4 text-yellow-600" />;
    return <AlertTriangle className="w-4 h-4 text-red-600" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading journeys...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => router.back()}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Journeys</h1>
            <p className="text-sm text-gray-500">Business journey health and coverage</p>
          </div>
        </div>
      </div>

      {/* Journey Cards */}
      <div className="grid gap-4">
        {journeys.map((journey) => (
          <div
            key={journey.id}
            className="bg-white border border-gray-200 rounded-lg overflow-hidden"
          >
            {/* Journey Card Header */}
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{journey.name}</h3>
                    <p className="text-sm text-gray-500">{journey.description}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <div className="text-sm text-gray-500">Risk</div>
                    {getRiskBadge(journey.risk_level)}
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-500">Coverage</div>
                    <div className={`text-lg font-semibold ${getCoverageColor(journey.coverage_score)}`}>
                      {journey.coverage_score}%
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-500">Testing Health</div>
                    <div className="flex items-center space-x-1">
                      {getTestingHealthIcon(journey.testing_health)}
                      <span className="text-sm font-medium">{journey.testing_health}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleExpand(journey.id)}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    {expandedJourney === journey.id ? (
                      <ChevronUp className="w-5 h-5" />
                    ) : (
                      <ChevronDown className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Expandable Details */}
            {expandedJourney === journey.id && (
              <div className="border-t border-gray-200 p-4 bg-gray-50">
                {journeyDetails[journey.id] ? (
                  <JourneyDetailsView details={journeyDetails[journey.id]} />
                ) : (
                  <div className="text-center text-gray-500 py-4">Loading details...</div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {journeys.length === 0 && (
        <div className="text-center py-12">
          <div className="text-gray-500">No journeys found</div>
        </div>
      )}
    </div>
  );
}

function JourneyDetailsView({ details }: { details: JourneyDetails }) {
  return (
    <div className="space-y-4">
      {/* Behaviors */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-2">Behaviors</h4>
        <div className="grid gap-2">
          {details.behaviors.map((behavior, index) => (
            <div
              key={index}
              className="flex items-center justify-between bg-white p-2 rounded border"
            >
              <span className="text-sm">{behavior.name}</span>
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">{behavior.risk_level}</span>
                <span className={`text-sm font-medium ${behavior.coverage >= 80 ? 'text-green-600' : behavior.coverage >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {behavior.coverage}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Coverage Breakdown */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-2">Coverage Breakdown</h4>
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-green-50 p-2 rounded border border-green-200">
            <div className="text-xs text-green-800">Covered</div>
            <div className="text-sm font-semibold text-green-900">{details.coverage.covered.length}</div>
          </div>
          <div className="bg-yellow-50 p-2 rounded border border-yellow-200">
            <div className="text-xs text-yellow-800">Partial</div>
            <div className="text-sm font-semibold text-yellow-900">{details.coverage.partially_covered.length}</div>
          </div>
          <div className="bg-red-50 p-2 rounded border border-red-200">
            <div className="text-xs text-red-800">Uncovered</div>
            <div className="text-sm font-semibold text-red-900">{details.coverage.uncovered.length}</div>
          </div>
        </div>
      </div>

      {/* Scenarios */}
      <div>
        <h4 className="text-sm font-semibold text-gray-900 mb-2">Scenarios</h4>
        <div className="text-sm text-gray-600">{details.scenarios} test scenarios</div>
      </div>

      {/* Risks */}
      {details.risks.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-2">Risks</h4>
          <div className="space-y-1">
            {details.risks.map((risk, index) => (
              <div key={index} className="text-sm text-red-600 flex items-center space-x-1">
                <AlertTriangle className="w-3 h-3" />
                <span>{risk}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
