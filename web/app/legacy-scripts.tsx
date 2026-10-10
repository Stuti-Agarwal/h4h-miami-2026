"use client";

import Script from "next/script";
import { useState } from "react";

// Load in the original order: Leaflet, then the main app script, then onboarding.
export default function LegacyScripts() {
  const [step, setStep] = useState(0);
  return (
    <>
      <Script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" onLoad={() => setStep(1)} />
      {step >= 1 && <Script src="/app.js" onLoad={() => setStep(2)} />}
      {step >= 2 && <Script src="/onboarding.js" />}
    </>
  );
}
