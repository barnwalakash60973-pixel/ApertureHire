import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { Button, Card } from "@/components/ui/primitives";
import { useAuth } from "@/context/AuthContext";
import { AuthApiError } from "@/api/auth";

const inputCls = "w-full rounded-lg border border-base-border bg-base-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-signal";

type Field = "name" | "email" | "mobileNumber" | "password" | "confirmPassword";

function validate(values: Record<Field, string>): Partial<Record<Field, string>> {
  const errors: Partial<Record<Field, string>> = {};
  if (!values.name.trim()) errors.name = "Enter your full name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email)) errors.email = "Enter a valid email address.";
  if (!/^\d{10}$/.test(values.mobileNumber)) errors.mobileNumber = "Enter a 10-digit mobile number.";
  if (values.password.length < 8) errors.password = "Password must be at least 8 characters.";
  if (values.confirmPassword !== values.password) errors.confirmPassword = "Passwords don't match.";
  return errors;
}

export function RegisterPage() {
  const [values, setValues] = useState<Record<Field, string>>({
    name: "",
    email: "",
    mobileNumber: "",
    password: "",
    confirmPassword: "",
  });
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [submitting, setSubmitting] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const errors = validate(values);

  const setField = (field: Field) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setValues((prev) => ({ ...prev, [field]: e.target.value }));

  const markTouched = (field: Field) => () => setTouched((prev) => ({ ...prev, [field]: true }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ name: true, email: true, mobileNumber: true, password: true, confirmPassword: true });
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await register({
      name: values.name.trim(),
      email: values.email.trim(),
      mobileNumber: values.mobileNumber.trim(),
      password: values.password,
    });
      toast.success("Account created successfully");
      navigate("/campaigns", { replace: true });
    } catch (err) {
      toast.error(err instanceof AuthApiError ? err.message : "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-md items-center px-6">
      <Card className="w-full p-8">
        <h1 className="mb-1 text-xl font-semibold text-ink">Create HR account</h1>
        <p className="mb-6 text-sm text-ink-muted">Set up your account to manage recruitment campaigns.</p>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-muted">Full name</label>
            <input
              value={values.name}
              onChange={setField("name")}
              onBlur={markTouched("name")}
              placeholder="Jane Doe"
              autoComplete="name"
              className={inputCls}
            />
            {touched.name && errors.name && <p className="mt-1 text-xs text-red-500">{errors.name}</p>}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-muted">Email</label>
            <input
              value={values.email}
              onChange={setField("email")}
              onBlur={markTouched("email")}
              placeholder="jane@company.com"
              autoComplete="email"
              className={inputCls}
            />
            {touched.email && errors.email && <p className="mt-1 text-xs text-red-500">{errors.email}</p>}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-muted">Mobile number</label>
            <input
              value={values.mobileNumber}
              onChange={setField("mobileNumber")}
              onBlur={markTouched("mobileNumber")}
              placeholder="9876543210"
              autoComplete="tel"
              className={inputCls}
            />
            {touched.mobileNumber && errors.mobileNumber && (
              <p className="mt-1 text-xs text-red-500">{errors.mobileNumber}</p>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-muted">Password</label>
            <input
              type="password"
              value={values.password}
              onChange={setField("password")}
              onBlur={markTouched("password")}
              autoComplete="new-password"
              className={inputCls}
            />
            {touched.password && errors.password && <p className="mt-1 text-xs text-red-500">{errors.password}</p>}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-ink-muted">Confirm password</label>
            <input
              type="password"
              value={values.confirmPassword}
              onChange={setField("confirmPassword")}
              onBlur={markTouched("confirmPassword")}
              autoComplete="new-password"
              className={inputCls}
            />
            {touched.confirmPassword && errors.confirmPassword && (
              <p className="mt-1 text-xs text-red-500">{errors.confirmPassword}</p>
            )}
          </div>

          <Button type="submit" disabled={submitting} className="w-full justify-center">
            {submitting ? "Creating account..." : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-muted">
          Already have an account?{" "}
          <Link to="/login" className="text-signal hover:underline">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}