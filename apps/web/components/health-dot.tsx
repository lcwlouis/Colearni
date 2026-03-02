"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api/client";

const POLL_INTERVAL_MS = 30_000;

export function HealthDot() {
    const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
    const [transitioning, setTransitioning] = useState(false);
    const prevStatus = useRef(status);

    useEffect(() => {
        if (status !== prevStatus.current && prevStatus.current !== "loading") {
            setTransitioning(true);
            const tid = setTimeout(() => setTransitioning(false), 600);
            prevStatus.current = status;
            return () => clearTimeout(tid);
        }
        prevStatus.current = status;
    }, [status]);

    useEffect(() => {
        const check = () => {
            apiClient.healthz()
                .then(() => setStatus("ok"))
                .catch(() => setStatus("error"));
        };

        check();
        const id = setInterval(check, POLL_INTERVAL_MS);
        return () => clearInterval(id);
    }, []);

    const cls = [
        "health-dot",
        status === "ok" ? "ok" : status === "error" ? "error" : "",
        transitioning ? "health-dot--transitioning" : "",
    ].filter(Boolean).join(" ");

    return (
        <span
            className={cls}
            title={status === "ok" ? "Connected to backend" : status === "error" ? "Backend unreachable" : "Checking..."}
        />
    );
}
