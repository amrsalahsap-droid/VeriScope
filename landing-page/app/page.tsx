import { Navbar } from "@/components/navbar";
import { HeroSection } from "@/components/hero-section";
import { TrustStrip } from "@/components/trust-strip";
import { FeaturesSection } from "@/components/features-section";
import { PRCommentSection } from "@/components/pr-comment-section";
import { FragilityMemorySection } from "@/components/fragility-memory-section";
import { ROISection } from "@/components/roi-section";
import { HowItWorksSection } from "@/components/how-it-works-section";
import { SecuritySection } from "@/components/security-section";
import { FinalCTASection } from "@/components/final-cta-section";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-white">
      <Navbar />
      <HeroSection />
      <TrustStrip />
      <FeaturesSection />
      <PRCommentSection />
      <FragilityMemorySection />
      <ROISection />
      <HowItWorksSection />
      <SecuritySection />
      <FinalCTASection />
      <Footer />
    </main>
  );
}
