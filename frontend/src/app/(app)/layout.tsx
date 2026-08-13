import { redirect } from 'next/navigation';

import Sidebar from '@/components/Sidebar';
import { getSession } from '@/lib/session';

/**
 * The authenticated shell.
 *
 * The redirect happens on the server, before any page in this group renders.
 * The previous version checked localStorage inside the Sidebar, which meant the
 * dashboard was fully server-rendered and sent to the browser before the client
 * decided to bounce the user. The data had already left the building.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  if (!session) {
    redirect('/login');
  }

  return (
    <>
      <Sidebar session={session} />
      <main className="relative ml-64 min-h-screen flex-1 overflow-x-hidden bg-paper">
        <div className="mx-auto max-w-6xl px-10 py-12">{children}</div>
      </main>
    </>
  );
}
