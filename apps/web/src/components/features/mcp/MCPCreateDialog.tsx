"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface MCPCreateDialogProps {
  onCreate: (direction: "sender" | "receiver", name: string) => Promise<void>;
  isCreating?: boolean;
}

export function MCPCreateDialog({ onCreate, isCreating }: MCPCreateDialogProps) {
  const [show, setShow] = useState(false);
  const [direction, setDirection] = useState<"sender" | "receiver">("sender");
  const [name, setName] = useState("");

  const handleSubmit = async () => {
    if (!name.trim()) return;
    await onCreate(direction, name.trim());
    setName("");
    setShow(false);
  };

  if (!show) {
    return (
      <Button variant="outline" size="sm" className="text-xs" onClick={() => setShow(true)}>
        <Plus size={12} className="mr-1" />
        Add Connection
      </Button>
    );
  }

  return (
    <div className="glow-card p-4 space-y-3">
      <h4 className="text-sm font-medium text-app-text">New Connection</h4>
      <div className="flex gap-2">
        <Button
          variant={direction === "sender" ? "default" : "outline"}
          size="sm"
          className="text-xs"
          onClick={() => setDirection("sender")}
        >
          Sender
        </Button>
        <Button
          variant={direction === "receiver" ? "default" : "outline"}
          size="sm"
          className="text-xs"
          onClick={() => setDirection("receiver")}
        >
          Receiver
        </Button>
      </div>
      <input
        type="text"
        placeholder="Connection name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        className="w-full bg-app-surface border border-app-border rounded-md px-3 py-1.5 text-sm text-app-text"
        autoFocus
      />
      <div className="flex gap-2">
        <Button size="sm" className="text-xs glow-button" onClick={handleSubmit} disabled={!name.trim() || isCreating}>
          {isCreating ? "Creating..." : "Create"}
        </Button>
        <Button variant="ghost" size="sm" className="text-xs" onClick={() => setShow(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
