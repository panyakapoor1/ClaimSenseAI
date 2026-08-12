import { redirect } from 'next/navigation';

import Sidebar from '@/components/Sidebar';
import { getSession } from '@/lib/session';

/**
 * The authenticated shell.
 *
 * The redirect happens on the server, before any page in this group renders.
 * The previous version checked localStorage inside the Sidebar, which meant the
 * dashboard was fully server-rendered and sent to the browser before the client
 * decided to bounce the user — the data had already left the building.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  if (!session) {
    redirect('/login');
  }

  return (
    <>
      <Sidebar session={session} />
      <main className="flex-1 ml-64 min-h-screen relative overflow-x-hidden bg-[#000000]">
        <div className="p-8 relative z-10 max-w-7xl mx-auto">{children}</div>
      </main>
    </>
  );
}
