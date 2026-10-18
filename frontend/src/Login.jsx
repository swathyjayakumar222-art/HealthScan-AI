import { useState } from "react";

export default function Login({ onLoginSuccess, onGoToSignup }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    setError("Login authentication is not connected yet.");
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="brand-icon">+</div>
        <h1>Welcome Back</h1>
        <p className="subtitle">Login to HealthScan AI</p>

        {error && <p className="error">{error}</p>}

        <label>Email Address</label>
        <input
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <label>Password</label>
        <input
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        <button type="submit" className="primary-btn">
          Login
        </button>

        <p className="switch-text">
          Don't have an account?{" "}
          <button
            type="button"
            className="text-btn"
            onClick={onGoToSignup}
          >
            Sign Up
          </button>
        </p>
      </form>
    </div>
  );
}