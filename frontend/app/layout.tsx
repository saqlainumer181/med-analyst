import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from '@/contexts/AuthContext'
import './globals.css'

// Configure the Inter font with specific subsets for optimization
// The 'latin' subset includes characters for most Western European languages
const inter = Inter({ 
  subsets: ['latin'],
  // Variable font gives us more flexibility with font weights
  variable: '--font-inter',
})

// Metadata for the application - this appears in browser tabs and search results
export const metadata: Metadata = {
  title: 'Med-Analyst | Natural Language to SQL Engine',
  description: 'Advanced medical data analysis through natural language queries. Transform complex medical data into actionable insights.',
  keywords: ['medical data', 'SQL', 'natural language', 'healthcare analytics', 'data analysis'],
  authors: [{ name: 'Med-Analyst Team' }],
  // Open Graph tags for social media sharing
  openGraph: {
    title: 'Med-Analyst | Natural Language to SQL Engine',
    description: 'Transform medical data into insights with natural language queries',
    type: 'website',
    locale: 'en_US',
  },
  // Twitter Card tags for Twitter sharing
  twitter: {
    card: 'summary_large_image',
    title: 'Med-Analyst | Natural Language to SQL Engine',
    description: 'Transform medical data into insights with natural language queries',
  },
  // Prevent search engines from indexing in development
  robots: process.env.NODE_ENV === 'production' ? 'index,follow' : 'noindex,nofollow',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} antialiased`}>
        {/* 
          AuthProvider wraps the entire application to provide authentication context
          This allows any component in the app to access user authentication state
        */}
        <AuthProvider>
          {/* Main content area with minimum full-screen height */}
          <main className="min-h-screen bg-gray-50">
            {children}
          </main>
          
          {/* 
            Global toast notifications component
            Position is set to top-right with custom styling that matches our theme
          */}
          <Toaster
            position="top-right"
            toastOptions={{
              // Default duration for all toasts
              duration: 4000,
              // Custom styling to match our medical theme
              style: {
                background: '#ffffff',
                color: '#1f2937',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
              },
              // Success toast styling
              success: {
                iconTheme: {
                  primary: '#10b981', // green-500
                  secondary: '#ffffff',
                },
              },
              // Error toast styling  
              error: {
                iconTheme: {
                  primary: '#ef4444', // red-500
                  secondary: '#ffffff',
                },
              },
              // Loading toast styling
              loading: {
                iconTheme: {
                  primary: '#0ea5e9', // medical-500
                  secondary: '#ffffff',
                },
              },
            }}
          />
        </AuthProvider>
      </body>
    </html>
  )
}