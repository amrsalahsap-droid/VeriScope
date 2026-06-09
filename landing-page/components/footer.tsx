"use client";

const links = {
  Product: [
    { label: "How It Works", href: "#how-it-works" },
    { label: "Pilot Program", href: "#pilot" },
    { label: "Pricing", href: "#" },
    { label: "Changelog", href: "#" },
  ],
  Docs: [
    { label: "Documentation", href: "#" },
    { label: "API Reference", href: "#" },
    { label: "GitHub App", href: "#" },
    { label: "Self-Hosted", href: "#" },
  ],
  Security: [
    { label: "Trust Center", href: "#" },
    { label: "Compliance", href: "#" },
    { label: "Data Handling", href: "#" },
  ],
  Company: [
    { label: "About", href: "#" },
    { label: "Careers", href: "#" },
    { label: "Blog", href: "#" },
  ],
  Contact: [
    { label: "hello@veriscope.dev", href: "mailto:hello@veriscope.dev" },
    { label: "Twitter", href: "#" },
    { label: "GitHub", href: "#" },
  ],
};

export function Footer() {
  return (
    <footer className="py-16 lg:py-20 bg-zinc-950 border-t border-zinc-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Top section */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 lg:gap-12 mb-16">
          {Object.entries(links).map(([category, items]) => (
            <div key={category}>
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">
                {category}
              </h4>
              <ul className="space-y-2.5">
                {items.map((item) => (
                  <li key={item.label}>
                    <a
                      href={item.href}
                      className="text-sm text-zinc-400 hover:text-white transition-colors duration-200"
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom section */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-8 border-t border-zinc-900">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-zinc-800 flex items-center justify-center">
              <span className="text-white text-xs font-bold">V</span>
            </div>
            <span className="text-sm font-semibold text-zinc-400">
              VERISCOPE
            </span>
          </div>
          <p className="text-xs text-zinc-600">
            © 2025 Veriscope. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
