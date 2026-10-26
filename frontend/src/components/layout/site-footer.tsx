import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t bg-muted/40">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 text-sm sm:grid-cols-3 sm:px-6">
        <div>
          <div className="font-semibold">HomeNest</div>
          <p className="mt-2 text-muted-foreground">
            Buy, rent or stay. A portfolio project showcasing MySQL, encryption and a modern frontend.
          </p>
        </div>
        <div className="space-y-2">
          <div className="font-semibold">Explore</div>
          <Link className="block text-muted-foreground hover:text-foreground" href="/search?mode=short_term_stay">
            Stays
          </Link>
          <Link className="block text-muted-foreground hover:text-foreground" href="/search?mode=sale">
            Homes for sale
          </Link>
          <Link className="block text-muted-foreground hover:text-foreground" href="/search?mode=long_term_rent">
            Rentals
          </Link>
        </div>
        <div className="space-y-2">
          <div className="font-semibold">Hosting</div>
          <Link className="block text-muted-foreground hover:text-foreground" href="/host/onboarding">
            Become a host
          </Link>
          <Link className="block text-muted-foreground hover:text-foreground" href="/host">
            Host dashboard
          </Link>
        </div>
      </div>
    </footer>
  );
}
