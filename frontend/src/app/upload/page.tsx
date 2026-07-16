import UploadWizard from "@/components/UploadWizard";

export default function UploadPage() {
  return (
    <div className="space-y-8">
      <header className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-2">
          New Claim Audit
        </h1>
        <p className="text-slate-400 text-lg">
          Submit documents to our multi-agent AI system for parsing and rule-based auditing.
        </p>
      </header>

      <UploadWizard />
    </div>
  );
}
