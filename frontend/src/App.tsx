import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { ThemeProvider } from "@/context/ThemeContext";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { Navbar } from "@/components/layout/Navbar";
import { LandingPage } from "@/pages/LandingPage";
import { ReviewPage } from "@/pages/ReviewPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { CampaignsListPage } from "@/pages/CampaignsListPage";
import { CampaignDashboardPage } from "@/pages/CampaignDashboardPage";
import { ResumeImportPage } from "@/pages/ResumeImportPage";
import { CampaignAssignmentPage } from "@/pages/CampaignAssignmentPage";
import { CampaignEvaluatePage } from "@/pages/CampaignEvaluatePage";
import { CampaignSelectedCandidatesPage } from "@/pages/CampaignSelectedCandidatesPage";
import { SubmissionPortalPage } from "@/pages/SubmissionPortalPage";

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <div className="min-h-screen bg-base">
            <Navbar />
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/review" element={<ReviewPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/submission/:token" element={<SubmissionPortalPage />} />
              <Route path="/campaigns" element={<ProtectedRoute><CampaignsListPage /></ProtectedRoute>} />
              <Route path="/campaigns/:campaignId" element={<ProtectedRoute><CampaignDashboardPage /></ProtectedRoute>} />
              <Route path="/campaigns/:campaignId/resumes" element={<ProtectedRoute><ResumeImportPage /></ProtectedRoute>} />
              <Route path="/campaigns/:campaignId/assignment" element={<ProtectedRoute><CampaignAssignmentPage /></ProtectedRoute>} />
              <Route path="/campaigns/:campaignId/evaluate" element={<ProtectedRoute><CampaignEvaluatePage /></ProtectedRoute>} />
              <Route path="/campaigns/:campaignId/selected" element={<ProtectedRoute><CampaignSelectedCandidatesPage /></ProtectedRoute>} />
            </Routes>
          </div>
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: "var(--color-surface)",
                color: "var(--color-ink)",
                border: "1px solid var(--color-border)",
                fontSize: "13px",
              },
            }}
          />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}