"use client"

import { useState } from "react"
import { Shield, Lock, FileText, Eye, EyeOff, AlertCircle, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useApp } from "@/lib/app-context"

export function RegisterPage() {
  const { register, setCurrentPage } = useApp()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [fullName, setFullName] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    
    if (!email || !password || !confirmPassword) {
      setError("All fields are required")
      return
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long")
      return
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match")
      return
    }

    setIsLoading(true)
    try {
      await register(email, password, fullName || undefined)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted">
      <div className="absolute inset-0 bg-[linear-gradient(rgba(11,94,215,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(11,94,215,0.03)_1px,transparent_1px)] bg-[size:32px_32px]" />

      <div className="relative z-10 flex w-full max-w-md flex-col items-center gap-6 px-4">
        {/* Government Emblem */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex size-16 items-center justify-center border-2 border-primary bg-primary/5">
            <Shield className="size-8 text-primary" />
          </div>
        </div>

        <Card className="w-full border border-border shadow-sm">
          <CardHeader className="gap-1 border-b border-border pb-4 text-center">
            <h1 className="text-lg font-semibold text-foreground">
              Create Your Account
            </h1>
            <p className="text-sm text-muted-foreground">
              Cyber Forensics Portal
            </p>
          </CardHeader>
          <CardContent className="pt-6">
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription className="text-sm">{error}</AlertDescription>
              </Alert>
            )}
            <form onSubmit={handleRegister} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="fullName" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Full Name (Optional)
                </Label>
                <Input
                  id="fullName"
                  type="text"
                  placeholder="Dir. Rajesh Kumar, IPS"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="h-10 border-border bg-background text-foreground"
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="email" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Official Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="officer@gov.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-10 border-border bg-background text-foreground"
                  required
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="password" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter New Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-10 border-border bg-background pr-10 text-foreground"
                    required
                    minLength={4}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="confirmPassword" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Confirm Password
                </Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Re-enter password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="h-10 border-border bg-background pr-10 text-foreground"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  >
                    {showConfirmPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="mt-2 h-10 w-full bg-primary font-medium text-primary-foreground hover:bg-primary/90"
                disabled={isLoading}
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                    Creating Account...
                  </span>
                ) : (
                  "Create Account"
                )}
              </Button>
            </form>

            <div className="mt-4 flex items-center justify-center gap-2 text-sm">
              <span className="text-muted-foreground">Already have an account?</span>
              <Button
                variant="link"
                className="h-auto p-0 text-primary"
                onClick={() => setCurrentPage("login")}
              >
                Sign In
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Security Indicators */}
        <div className="flex w-full flex-wrap items-center justify-center gap-4">
          <SecurityIndicator icon={Lock} label="AES-256 Encrypted" />
          <SecurityIndicator icon={Shield} label="Secure Registration" />
          <SecurityIndicator icon={FileText} label="Audit Logged" />
        </div>

        <p className="text-[10px] text-muted-foreground">
          Unauthorized access is a punishable offense under IT Act, 2000
        </p>
      </div>
    </div>
  )
}

function SecurityIndicator({ icon: Icon, label }: { icon: React.ComponentType<{ className?: string }>, label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <Icon className="size-3 text-success" />
      <span className="text-[10px] font-medium text-success">{label}</span>
    </div>
  )
}

