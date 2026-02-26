"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

export function HealthDot() {
    const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

    useEffect(() => {
        apiClient.healthz()
            .then(() => setStatus("ok"))
            .catch(() => setStatus("error"));
    }, []);

    return (
        <span
            className={`health-dot ${status === "ok" ? "ok" : status === "error" ? "error" : ""}`}
            title={status === "ok" ? "Connected to backend" : status === "error" ? "Backend unreachable" : "Checking..."}
        />
    );
}
