/* ============================================================
   Profource Marktmonitor — shared auth helpers
   Include this AFTER the supabase-js <script> tag on every page.
   ============================================================ */

// Guard: if this script is accidentally included twice on the same page
// (duplicate <script src="auth.js"> tag, caching quirk, etc.), skip the
// second run instead of crashing with "Identifier already declared".
if (!window.__pfAuthLoaded) {
  window.__pfAuthLoaded = true;

  // --- 1. Fill these in with your Supabase project's values ---
  // Project Settings > API > Project URL / anon public key
const SUPABASE_URL = 'https://lzbzwfxdcszirbnpexij.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx6Ynp3ZnhkY3N6aXJibnBleGlqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODUyMjcwNzAsImV4cCI6MjEwMDgwMzA3MH0.DX31BPrjI1vjOIgwWJfCbxnbmrZBJBO7ilftbzWD6Yw';

  window.supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  // --- 2. Get the current session, or null if not logged in ---
  window.getSession = async function getSession() {
    const { data: { session } } = await window.supabase.auth.getSession();
    return session;
  };

  // --- 3. Get the current user's profile row (role + status), or null ---
  window.getProfile = async function getProfile() {
    const session = await window.getSession();
    if (!session) return null;
    const { data, error } = await window.supabase
      .from('profiles')
      .select('id, email, role, status')
      .eq('id', session.user.id)
      .single();
    if (error) return null;
    return data;
  };

  // --- 4. Call at the top of any protected page (e.g. index.html) ---
  // Redirects to login if not signed in, or if the account is blocked.
  window.requireUser = async function requireUser() {
    const profile = await window.getProfile();
    if (!profile) {
      window.location.href = 'login.html';
      return null;
    }
    if (profile.status === 'blocked') {
      await window.supabase.auth.signOut();
      alert('Dit account is geblokkeerd. Neem contact op met een beheerder.');
      window.location.href = 'login.html';
      return null;
    }
    return profile;
  };

  // --- 5. Call at the top of admin.html ---
  // Redirects to the dashboard if the user isn't an admin.
  window.requireAdmin = async function requireAdmin() {
    const profile = await window.requireUser();
    if (!profile) return null;
    if (profile.role !== 'admin') {
      window.location.href = 'index.html';
      return null;
    }
    return profile;
  };

  // --- 6. Logout helper — wire this to any "Uitloggen" button ---
  window.logout = async function logout() {
    await window.supabase.auth.signOut();
    window.location.href = 'login.html';
  };
}
