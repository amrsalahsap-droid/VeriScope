"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const navLinks = [
  { label: "Product", href: "#product" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Pilot Program", href: "#pilot" },
  { label: "Security", href: "#security" },
  { label: "Docs", href: "#docs" },
];

export function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50">
      <nav className="mx-4 mt-4">
        <div className="max-w-7xl mx-auto">
          <div className={`flex items-center justify-between h-14 px-6 rounded-full transition-all duration-500 ${scrolled ? "bg-white/90 backdrop-blur-2xl border-zinc-200/80 shadow-lg shadow-zinc-200/20" : "bg-white/60 backdrop-blur-xl border-zinc-200/40 shadow-sm"} border`}>
            {/* Logo */}
            <a href="/" className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-zinc-900 flex items-center justify-center">
                <span className="text-white font-bold text-sm">V</span>
              </div>
              <span className="font-semibold text-zinc-900 tracking-tight">
                VERISCOPE
              </span>
            </a>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-8">
              {navLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="relative text-sm font-medium text-zinc-600 hover:text-zinc-900 transition-colors duration-300 group"
                >
                  {link.label}
                  <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-zinc-900 transition-all duration-300 group-hover:w-full rounded-full" />
                </a>
              ))}
            </div>

            {/* Desktop CTA Buttons */}
            <div className="hidden md:flex items-center gap-3">
              <Button variant="ghost" size="sm" className="text-zinc-600" asChild>
                <a href="/contact">Book Pilot</a>
              </Button>
              <Button size="sm" asChild>
                <a href="/signup">Get Early Access</a>
              </Button>
            </div>

            {/* Mobile Menu Button */}
            <button
              className="md:hidden p-2 text-zinc-600"
              onClick={() => setIsOpen(!isOpen)}
              aria-label="Toggle menu"
            >
              {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>

          {/* Mobile Menu */}
          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="md:hidden mt-2 p-4 rounded-2xl bg-white/95 backdrop-blur-xl border border-zinc-200/50 shadow-lg"
              >
                <div className="flex flex-col gap-2">
                  {navLinks.map((link) => (
                    <a
                      key={link.label}
                      href={link.href}
                      className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50 rounded-lg transition-colors"
                      onClick={() => setIsOpen(false)}
                    >
                      {link.label}
                    </a>
                  ))}
                  <div className="pt-2 mt-2 border-t border-zinc-100 flex flex-col gap-2">
                    <Button variant="ghost" size="sm" className="justify-center" asChild>
                      <a href="/contact">Book Pilot</a>
                    </Button>
                    <Button size="sm" className="justify-center" asChild>
                      <a href="/signup">Get Early Access</a>
                    </Button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </nav>
    </header>
  );
}
