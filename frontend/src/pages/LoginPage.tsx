import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { Button, Card } from "@/components/ui/primitives";
import { useAuth } from "@/context/AuthContext";
import { AuthApiError } from "@/api/auth";

const inputCls = "w-full rounded-lg border border-base-border bg-base-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-signal";

type Field = "identifier" | "password";

function validate(values: Record<Field, string>): Partial<Record<Field, string>> {
  const errors: Partial<Record<Field, string>> = {};
  if (!values.identifier.trim()) errors.identifier = "Enter your email or mobile number.";
  if (!values.password) errors.password = "Enter your password.";
  return errors;
}

export function LoginPage() {
  const [values, setValues] = useState<Record<Field, string>>({ identifier: "", password: "" });
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/campaigns";
  const errors = validate(values);

  const setField = (field: Field) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setValues((prev) => ({ ...prev, [field]: e.target.value }));

  const markTouched = (field: Field) => () => setTouched((prev) => ({ ...prev, [field]: true }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ identifier: true, password: true });
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await login(values.identifier.trim(), values.password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      toast.error(err instanceof AuthApiError ? err.message : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-md items-center px-6">
      <Card className="w-full p-8">
        <h1 className="mb-1 text-xl font-semibold text-ink">HR Login</h1>
        <p className="mb-6 text-sm text-ink-muted">Sign in to manage your recruitment campaigns.</p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-muted">Email or mobile number</label>
            <input
              value={values.identifier}
              onChange={setField("identifier")}
              onBlur={markTouched("identifier")}
              placeholder="jane@company.com or +1 555 123 4567"
              autoComplete="username"
              className={inputCls}
            />
            {touched.identifier && errors.identifier && (
              <p className="mt-1 text-xs text-red-500">{errors.identifier}</p>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-xs font-medium text-ink-muted">Password</label>
              <Link to="/forgot-password" className="text-xs text-signal hover:underline">
                Forgot password?
              </Link>
            </div>
            <input
              type="password"
              value={values.password}
              onChange={setField("password")}
              onBlur={markTouched("password")}
              autoComplete="current-password"
              className={inputCls}
            />
            {touched.password && errors.password && <p className="mt-1 text-xs text-red-500">{errors.password}</p>}
          </div>

          <Button type="submit" disabled={submitting} className="w-full justify-center">
            {submitting ? "Signing in..." : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          Don't have an account?{" "}
          <Link to="/register" className="text-signal hover:underline">
            Create account
          </Link>
        </p>
      </Card>
    </div>
  );
}