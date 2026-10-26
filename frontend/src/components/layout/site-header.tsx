import { HouseIcon } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";
import { VerifyBanner } from "./verify-banner";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-primary">
          <HouseIcon className="size-6" />
          <span>HomeNest</span>
        </Link>
        <nav className="ml-6 hidden items-center gap-1 text-sm font-medium md:flex">
          <Link href="/search?mode=sale" className="rounded-full px-3 py-2 hover:bg-muted">
            Buy
          </Link>
          <Link href="/search?mode=long_term_rent" className="rounded-full px-3 py-2 hover:bg-muted">
            Rent
          </Link>
          <Link href="/search?mode=short_term_stay" className="rounded-full px-3 py-2 hover:bg-muted">
            Stays
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
      <VerifyBanner />
    </header>
  );
}
