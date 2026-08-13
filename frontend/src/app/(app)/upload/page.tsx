import UploadWizard from '@/components/UploadWizard';
import PageHeader from '@/components/PageHeader';

export default function UploadPage() {
  return (
    <div>
      <PageHeader
        eyebrow="New audit"
        title="Upload a claim"
        description="The bill is parsed line by line and each line is decided against the policy you supply. Nothing is adjudicated against a policy the claim did not come with."
      />

      <div className="mt-10">
        <UploadWizard />
      </div>
    </div>
  );
}
