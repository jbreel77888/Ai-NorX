"use client";

import { toast as sonnerToast, Toaster as SonnerToaster } from "sonner";

export const toast = sonnerToast;

export function Toaster() {
  return (
    <SonnerToaster
      position="top-center"
      toastOptions={{
        style: {
          fontFamily: "inherit",
        },
      }}
      dir="rtl"
    />
  );
}
