"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { API, extractErrorMessage } from "./api";
import styles from "../app/login/login.module.css";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: "standard" | "icon";
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              shape?: "rectangular" | "pill" | "circle" | "square";
              logo_alignment?: "left" | "center";
              width?: number | string;
            }
          ) => void;
          prompt?: () => void;
        };
      };
    };
  }
}

interface GoogleSignInButtonProps {
  busy?: boolean;
  setBusy: (busy: boolean) => void;
  setError: (error: string) => void;
  text?: "continue_with" | "signin_with" | "signup_with";
}

function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path
        d="M17.64 9.2045c0-.6381-.0573-1.2518-.1636-1.8409H9v3.4814h4.8436c-.2086 1.125-.8427 2.0782-1.7959 2.7164v2.2581h2.9087c1.7018-1.5668 2.6836-3.874 2.6836-6.615z"
        fill="#4285F4"
      />
      <path
        d="M9 18c2.43 0 4.4673-.806 5.9564-2.1805l-2.9087-2.2581c-.8059.54-1.8368.859-3.0477.859-2.344 0-4.3282-1.5831-5.036-3.7104H.9574v2.3318C2.4382 15.9832 5.4818 18 9 18z"
        fill="#34A853"
      />
      <path
        d="M3.964 10.71c-.18-.54-.2822-1.1168-.2822-1.71s.1023-1.17.2822-1.71V4.9582H.9573A8.9965 8.9965 0 000 9c0 1.4523.3477 2.8268.9573 4.0418L3.964 10.71z"
        fill="#FBBC05"
      />
      <path
        d="M9 3.5795c1.3214 0 2.5077.4541 3.4405 1.346l2.5813-2.5814C13.4632.9299 11.4259 0 9 0 5.4818 0 2.4382 2.0168.9574 4.9582L3.964 7.29C4.6718 5.1627 6.656 3.5795 9 3.5795z"
        fill="#EA4335"
      />
    </svg>
  );
}

export default function GoogleSignInButton({
  busy = false,
  setBusy,
  setError,
  text = "continue_with",
}: GoogleSignInButtonProps) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const hasRenderedRef = useRef(false);
  const [rendered, setRendered] = useState(false);

  const clientId =
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
    "545630055112-k1k5c5dvhhegts3ffpqmb15oi3f17hlr.apps.googleusercontent.com";

  const handleCredentialResponse = useCallback(
    async (response: { credential?: string }) => {
      if (!response?.credential) {
        setError("No Google credential received");
        return;
      }
      setBusy(true);
      setError("");
      try {
        const res = await fetch(API + "/auth/google", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: response.credential }),
        });
        const d = await res.json();
        if (!res.ok) {
          throw new Error(extractErrorMessage(d, "Google sign-in failed"));
        }
        localStorage.setItem("rivu_access_token", d.tokens.access_token);
        localStorage.setItem("rivu_refresh_token", d.tokens.refresh_token);
        localStorage.setItem("rivu_user", JSON.stringify(d.user));
        localStorage.setItem("rivu_org", JSON.stringify(d.organization));
        router.push("/dashboard");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to sign in with Google");
      } finally {
        setBusy(false);
      }
    },
    [router, setBusy, setError]
  );

  const renderGoogleButton = useCallback(() => {
    if (
      typeof window === "undefined" ||
      !window.google?.accounts?.id ||
      !containerRef.current ||
      hasRenderedRef.current
    ) {
      return;
    }
    try {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: handleCredentialResponse,
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      // Google owns the contents of this mount node. Keep it separate from
      // React-rendered children so React never reconciles Google's iframe DOM.
      window.google.accounts.id.renderButton(containerRef.current, {
        type: "standard",
        theme: "filled_black",
        size: "large",
        shape: "rectangular",
        text,
        logo_alignment: "left",
        width: 375,
      });
      hasRenderedRef.current = true;
      setTimeout(() => setRendered(true), 0);
    } catch (err) {
      console.error("Google Identity Services renderButton error:", err);
    }
  }, [clientId, handleCredentialResponse, text]);

  useEffect(() => {
    const timer = setTimeout(() => {
      renderGoogleButton();
    }, 0);
    const interval = setInterval(() => {
      if (window.google?.accounts?.id && !rendered) {
        renderGoogleButton();
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [renderGoogleButton, rendered]);

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={renderGoogleButton}
      />
      <div className={styles.googleContainer}>
        <div className={styles.googleBtnWrapper}>
          <div ref={containerRef} />
          {!rendered && (
            <button
              type="button"
              className={styles.googlePlaceholderBtn}
              onClick={() => {
                if (window.google?.accounts?.id) {
                  renderGoogleButton();
                } else {
                  setError("Google Sign-In is initializing. Please retry in a moment.");
                }
              }}
              disabled={busy}
              aria-label="Continue with Google"
            >
              <GoogleLogo />
              <span>Continue with Google</span>
            </button>
          )}
        </div>
      </div>
    </>
  );
}
