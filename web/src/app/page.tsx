"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth) {
      router.replace("/login");
      return;
    }
    if (auth.role === "parent") {
      router.replace("/parent/report/weekly");
    } else if (auth.role === "admin") {
      router.replace("/admin/dashboard");
    } else {
      // Student: check onboarding status before routing
      const onboarded = localStorage.getItem("onboarding_completed");
      if (onboarded === "true") {
        router.replace("/dashboard");
      } else {
        router.replace("/onboarding");
      }
    }
  }, [router]);
  return null;
}
