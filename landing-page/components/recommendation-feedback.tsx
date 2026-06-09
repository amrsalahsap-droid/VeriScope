"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, AlertCircle, Minus, Maximize2, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface RecommendationFeedbackProps {
  recommendationRunId: string;
  existingFeedback?: string;
  existingComment?: string;
}

type FeedbackType = "USEFUL" | "NOT_USEFUL" | "MISSING_TESTS" | "TOO_BROAD" | "TOO_NARROW" | null;

const feedbackOptions = [
  { value: "USEFUL" as const, label: "Useful", icon: ThumbsUp },
  { value: "NOT_USEFUL" as const, label: "Not useful", icon: ThumbsDown },
  { value: "MISSING_TESTS" as const, label: "Missing important tests", icon: AlertCircle },
  { value: "TOO_BROAD" as const, label: "Too broad", icon: Maximize2 },
  { value: "TOO_NARROW" as const, label: "Too narrow", icon: Minus },
];

export function RecommendationFeedback({
  recommendationRunId,
  existingFeedback,
  existingComment,
}: RecommendationFeedbackProps) {
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackType>(
    (existingFeedback as FeedbackType) || null
  );
  const [comment, setComment] = useState(existingComment || "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showCommentBox, setShowCommentBox] = useState(!!existingComment);

  const handleFeedbackSelect = async (feedbackType: FeedbackType) => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_feedback: feedbackType,
        }),
      });

      if (!response.ok) throw new Error("Failed to submit feedback");

      setSelectedFeedback(feedbackType);
      toast.success("Feedback recorded", {
        description: "Thank you for your feedback!",
      });
    } catch (error) {
      toast.error("Failed to record feedback", {
        description: "Please try again later.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCommentSubmit = async () => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      const response = await fetch(`/api/recommendations/${recommendationRunId}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback_comment: comment,
        }),
      });

      if (!response.ok) throw new Error("Failed to submit comment");

      toast.success("Comment recorded", {
        description: "Thank you for your input!",
      });
    } catch (error) {
      toast.error("Failed to record comment", {
        description: "Please try again later.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-zinc-950/40 border border-zinc-800/30 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-zinc-400" />
        <h3 className="text-sm font-medium text-zinc-200">Was this recommendation useful?</h3>
      </div>

      <div className="flex flex-wrap gap-2">
        {feedbackOptions.map((option) => {
          const Icon = option.icon;
          const isSelected = selectedFeedback === option.value;

          return (
            <Button
              key={option.value}
              variant={isSelected ? "default" : "outline"}
              size="sm"
              onClick={() => handleFeedbackSelect(option.value)}
              disabled={isSubmitting}
              className={
                isSelected
                  ? "bg-blue-600 hover:bg-blue-700 text-white border-blue-600"
                  : "bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border-zinc-700"
              }
            >
              <Icon className="w-3.5 h-3.5 mr-1.5" />
              {option.label}
            </Button>
          );
        })}
      </div>

      {(selectedFeedback || showCommentBox) && (
        <div className="space-y-2 pt-2 border-t border-zinc-800/40">
          <label className="text-xs text-zinc-400">
            Tell us what was wrong or missing (optional)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a comment..."
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              onKeyDown={(e) => {
                if (e.key === "Enter" && comment.trim()) {
                  handleCommentSubmit();
                }
              }}
            />
            <Button
              size="sm"
              onClick={handleCommentSubmit}
              disabled={isSubmitting || !comment.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {isSubmitting ? "Saving..." : "Send"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
