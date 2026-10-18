import { useState } from "react";

export default function Signup({ onSignupSuccess, onSignup, onLogin }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (password.length < 6) {
      setError("Password must contain at least 6 characters.");
      return;
    }

    try {
      if (onSignup) {
        await onSignup({
          name: name.trim(),
          email: email.trim(),
          password,
        });
      } else {
        setError("Account creation is not connected to the backend.");
        return;
      }

      if (onSignupSuccess) {
        onSignupSuccess();
      }
    } catch (err) {
      setError(err.message || "Signup failed. Please try again.");
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="brand-icon">+</div>
        <h1>Create Account</h1>
        <p className="subtitle">Join HealthScan AI</p>

        {error && <p className="error">{error}</p>}

        <label>Full Name</label>
        <input
          type="text"
          placeholder="Enter your full name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />

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
          placeholder="At least 6 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={6}
          required
        />

        <button type="submit" className="primary-btn">
          Create Account
        </button>

        <p className="switch-text">
          Already have an account?{" "}
          <button
            type="button"
            className="text-btn"
            onClick={() => {
              if (onLogin) onLogin();
              else if (onSignupSuccess) onSignupSuccess();
            }}
          >
            Login
          </button>
        </p>
      </form>
    </div>
  );
}