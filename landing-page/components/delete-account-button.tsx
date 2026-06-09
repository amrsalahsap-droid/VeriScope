"use client";

import { useState } from "react";
import { Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { signOut } from "next-auth/react";

interface DeleteAccountButtonProps {
  backendToken: string | null | undefined;
}

export function DeleteAccountButton({ backendToken }: DeleteAccountButtonProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleDelete = async () => {
    console.log("handleDelete called, backendToken:", backendToken ? "exists" : "missing");
    if (!backendToken) {
      toast.error("Authentication error", {
        description: "No backend token found"
      });
      return;
    }

    setIsDeleting(true);
    try {
      const res = await fetch("/api/auth/delete-account", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ backendToken }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        console.error("Failed to delete user:", errorText);
        let errorMessage = `Status: ${res.status}`;
        try {
          const errorJson = JSON.parse(errorText);
          if (errorJson.error) {
            errorMessage = errorJson.error;
          }
          if (errorJson.details) {
            errorMessage += ` - ${errorJson.details}`;
          }
        } catch {
          errorMessage = errorText || errorMessage;
        }
        toast.error("Failed to delete account", {
          description: errorMessage
        });
        setIsDeleting(false);
        return;
      }

      toast.success("Account deleted successfully");
      
      // Sign out NextAuth session and redirect to landing page
      setTimeout(async () => {
        await signOut({ redirectTo: "/" });
      }, 1000);
    } catch (err) {
      console.error("Error deleting user:", err);
      toast.error("Error deleting account", {
        description: err instanceof Error ? err.message : "Unknown error"
      });
      setIsDeleting(false);
    }
  };

  if (showConfirm) {
    return (
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="w-7 h-7 text-zinc-500 hover:text-white hover:bg-zinc-900/60 transition-colors duration-150"
          onClick={() => setShowConfirm(false)}
          title="Cancel"
        >
          ✕
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="w-7 h-7 text-red-500 hover:text-red-400 hover:bg-red-500/10 transition-colors duration-150"
          onClick={handleDelete}
          disabled={isDeleting}
          title="Confirm delete"
        >
          {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      className="w-7 h-7 text-red-500 hover:text-red-400 hover:bg-red-500/10 transition-colors duration-150"
      onClick={() => setShowConfirm(true)}
      title="Delete account"
    >
      <Trash2 className="w-3.5 h-3.5" />
    </Button>
  );
}
