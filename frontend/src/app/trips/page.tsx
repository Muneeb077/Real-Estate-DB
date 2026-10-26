"use client";

import { PageTitle, RequireAuth } from "@/components/auth/require-auth";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { OffersList, StaysList, ViewingsList } from "./lists";

export default function TripsPage() {
  return (
    <RequireAuth>
      {() => (
        <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
          <PageTitle title="Trips & offers" description="Your stays, offers, rental applications and viewings." />
          <Tabs defaultValue="stays">
            <TabsList>
              <TabsTrigger value="stays">Stays</TabsTrigger>
              <TabsTrigger value="offers">Offers</TabsTrigger>
              <TabsTrigger value="viewings">Viewings</TabsTrigger>
            </TabsList>
            <TabsContent value="stays" className="pt-4">
              <StaysList />
            </TabsContent>
            <TabsContent value="offers" className="pt-4">
              <OffersList />
            </TabsContent>
            <TabsContent value="viewings" className="pt-4">
              <ViewingsList />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </RequireAuth>
  );
}
