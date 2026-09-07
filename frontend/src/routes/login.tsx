import { createFileRoute, redirect } from "@tanstack/react-router"

import { AuthLayout } from "@/components/Common/AuthLayout"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Log In",
      },
    ],
  }),
})

// Placeholder login screen. The phone-number + OTP flow is implemented in a
// later task (see PROJECT_SPEC.md section 9); this keeps the route tree and the
// `_layout` redirect target valid in the meantime.
function Login() {
  return (
    <AuthLayout>
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Phone number sign-in is coming soon.
        </p>
      </div>
    </AuthLayout>
  )
}