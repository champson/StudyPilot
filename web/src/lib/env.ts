export const env = {
  NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1",
};

// Validate critical environment variables in production
if (process.env.NODE_ENV === "production" && !process.env.NEXT_PUBLIC_API_BASE) {
  console.warn("⚠️ Warning: NEXT_PUBLIC_API_BASE is not defined in production environment.");
}
