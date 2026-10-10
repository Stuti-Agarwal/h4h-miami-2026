import { markup } from "./markup";
import LegacyScripts from "./legacy-scripts";

// Static markup + the original imperative JS (public/app.js, public/onboarding.js).
export default function Page() {
  return (
    <>
      <div style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: markup }} />
      <LegacyScripts />
    </>
  );
}
