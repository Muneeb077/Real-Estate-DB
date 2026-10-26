"use client";

import {
  BellIcon,
  BuildingIcon,
  CalendarIcon,
  HeartIcon,
  LogOutIcon,
  MenuIcon,
  MessageSquareIcon,
  SettingsIcon,
  ShieldIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { hasRole, useLogout, useMe } from "@/lib/auth";

export function UserMenu() {
  const { data: me, isLoading } = useMe();
  const logout = useLogout();
  const router = useRouter();

  if (isLoading) return <div className="size-9 animate-pulse rounded-full bg-muted" />;

  if (!me) {
    return (
      <div className="flex items-center gap-2">
        <Button variant="ghost" render={<Link href="/login" />} nativeButton={false}>
          Log in
        </Button>
        <Button render={<Link href="/signup" />} nativeButton={false}>
          Sign up
        </Button>
      </div>
    );
  }

  const go = (href: string) => () => router.push(href);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="outline" className="h-10 gap-2 rounded-full pr-1 pl-3" aria-label="Account menu" />
        }
      >
        <MenuIcon />
        <Avatar className="size-8">
          <AvatarImage src={me.avatar_url ?? undefined} alt="" />
          <AvatarFallback>{me.display_name.slice(0, 1)}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            <div className="font-medium text-foreground">{me.display_name}</div>
            <div className="truncate text-xs font-normal">{me.email}</div>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={go("/trips")}>
          <CalendarIcon /> Trips & offers
        </DropdownMenuItem>
        <DropdownMenuItem onClick={go("/wishlists")}>
          <HeartIcon /> Wishlist
        </DropdownMenuItem>
        <DropdownMenuItem onClick={go("/inbox")}>
          <MessageSquareIcon /> Inbox
        </DropdownMenuItem>
        <DropdownMenuItem onClick={go("/notifications")}>
          <BellIcon /> Notifications
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {hasRole(me, "host") ? (
          <DropdownMenuItem onClick={go("/host")}>
            <BuildingIcon /> Host dashboard
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onClick={go("/host/onboarding")}>
            <BuildingIcon /> Become a host
          </DropdownMenuItem>
        )}
        {hasRole(me, "admin") && (
          <DropdownMenuItem onClick={go("/admin")}>
            <ShieldIcon /> Admin
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={go("/account")}>
          <SettingsIcon /> Account & security
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout}>
          <LogOutIcon /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
