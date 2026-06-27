import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <section className="panel not-found-panel">
      <h2>Page unavailable</h2>
      <p className="muted">The requested training log page does not exist.</p>
      <Link className="primary-button compact-button" to="/">
        Current workout
      </Link>
    </section>
  );
}