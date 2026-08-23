import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { Button, Card } from "@/components/ui/primitives";
import { forgotPassword, resetPassword, AuthApiError } from "@/api/auth";

const inputCls = "w-full rounded-lg border border-base-border bg-base-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-signal";

export function ForgotPasswordPage() {
  const [step, setStep] = useState<"request" | "reset">("request");
  const [identifier, setIdentifier] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const requestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!identifier.trim()) return;
    setSubmitting(true);
    try {
      const result = await forgotPassword(identifier.trim());
      toast.success(result.message);
      setStep("reset");
    } catch (err) {
      toast.error(err instanceof AuthApiError ? err.message : "Request failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const submitReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (otp.length !== 6 || newPassword.length < 8) return;
    setSubmitting(true);
    try {
      await resetPassword(identifier.trim(), otp, newPassword);
      toast.success("Password reset. Please sign in with your new password.");
      navigate("/login", { replace: true });
    } catch (err) {
      toast.error(err instanceof AuthApiError ? err.message : "Reset failed - check the code and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-md items-center px-6">
      <Card className="w-full p-8">
        {step === "request" ? (
          <>
            <h1 className="mb-1 text-xl font-semibold text-ink">Forgot password</h1>
            <p className="mb-6 text-sm text-ink-muted">
              Enter your email or mobile number. If an account exists, we'll email a 6-digit reset code.
            </p>
            <form onSubmit={requestOtp} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-muted">Email or mobile number</label>
                <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} className={inputCls} autoFocus />
              </div>
              <Button type="submit" disabled={submitting || !identifier.trim()} className="w-full justify-center">
                {submitting ? "Sending..." : "Send reset code"}
              </Button>
            </form>
          </>
        ) : (
          <>
            <h1 className="mb-1 text-xl font-semibold text-ink">Enter reset code</h1>
            <p className="mb-6 text-sm text-ink-muted">
              Check the email for {identifier} for a 6-digit code. It expires in 10 minutes.
            </p>
            <form onSubmit={submitReset} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-muted">6-digit code</label>
                <input
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  maxLength={6}
                  className={inputCls + " tracking-[0.3em] text-center"}
                  autoFocus
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-muted">New password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className={inputCls}
                />
              </div>
              <Button type="submit" disabled={submitting || otp.length !== 6 || newPassword.length < 8} className="w-full justify-center">
                {submitting ? "Resetting..." : "Reset password"}
              </Button>
              <button
                type="button"
                onClick={() => setStep("request")}
                className="w-full text-center text-xs text-ink-muted hover:text-ink"
              >
                Use a different email/mobile number
              </button>
            </form>
          </>
        )}
        <p className="mt-6 text-center text-xs text-ink-muted">
          <Link to="/login" className="text-signal hover:underline">Back to sign in</Link>
        </p>
      </Card>
    </div>
  );
}
