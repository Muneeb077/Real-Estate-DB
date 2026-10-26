"use client";

import { RequireAuth, PageTitle } from "@/components/auth/require-auth";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { PrivacyTab } from "./privacy-tab";
import { ProfileTab } from "./profile-tab";
import { SecurityTab } from "./security-tab";

export default function AccountPage() {
  return (
    <RequireAuth>
      {(me) => (
        <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
          <PageTitle title="Account" description={me.email} />
          <Tabs defaultValue="profile">
            <TabsList>
              <TabsTrigger value="profile">Profile</TabsTrigger>
              <TabsTrigger value="security">Security</TabsTrigger>
              <TabsTrigger value="privacy">Privacy</TabsTrigger>
            </TabsList>
            <TabsContent value="profile" className="pt-4">
              <ProfileTab />
            </TabsContent>
            <TabsContent value="security" className="pt-4">
              <SecurityTab />
            </TabsContent>
            <TabsContent value="privacy" className="pt-4">
              <PrivacyTab />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </RequireAuth>
  );
}
