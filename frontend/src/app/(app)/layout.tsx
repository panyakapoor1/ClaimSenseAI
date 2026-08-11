import Sidebar from "@/components/Sidebar";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen relative overflow-x-hidden bg-[#000000]">
        <div className="p-8 relative z-10 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </>
  );
}
