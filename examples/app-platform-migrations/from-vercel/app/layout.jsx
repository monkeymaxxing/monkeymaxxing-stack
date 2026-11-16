export const metadata = { title: 'Private customer portal', description: 'Keep private records, documents, and record-count reports.' }
export default function Layout({ children }) {
  return <html lang="en"><body style={{ maxWidth: 800, margin: '2rem auto', padding: '0 1rem', fontFamily: 'system-ui' }}>{children}</body></html>
}
