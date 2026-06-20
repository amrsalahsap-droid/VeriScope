import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";
import { SignJWT, jwtVerify } from "jose";

export const { handlers, auth, signIn, signOut } = NextAuth({
  session: {
    strategy: "jwt",
  },
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
      profile(profile) {
        return {
          id: profile.id.toString(),
          name: profile.name || profile.login,
          email: profile.email,
          image: profile.avatar_url,
          login: profile.login,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account, profile }) {
      if (user) {
        token.id = user.id;
        // Use login if available on user object (from profile callback above)
        token.github_username = (user as any).login || (profile as any)?.login;
      }
      return token;
    },
    async session({ session, token }) {
      const secret = new TextEncoder().encode(
        process.env.STATE_SECRET_KEY || "veriscope-state-secret-key-change-in-prod"
      );

      // Sign a JWT with HS256 to send to the FastAPI backend
      const backendToken = await new SignJWT({
        sub: (token.sub as string) || (token.id as string) || "",
        email: session.user.email,
        name: session.user.name,
        image: session.user.image,
        auth_provider: "github",
        provider_user_id: (token.sub as string) || (token.id as string) || "",
      })
        .setProtectedHeader({ alg: "HS256", typ: "JWT" })
        .setIssuedAt()
        .setExpirationTime("24h")
        .sign(secret);

      // Add backend token to the session object
      session.backendToken = backendToken;

      // Workspace creation is now handled by backend get_current_user dependency
      // Backend is the single source of truth for user/workspace resolution

      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});

// Extend type declarations for NextAuth
declare module "next-auth" {
  interface Session {
    backendToken?: string;
  }
}
