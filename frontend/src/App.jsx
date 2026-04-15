import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import ImpersonationBar from './components/ImpersonationBar';
import Login from './pages/Login';
import CostModelBuilder from './pages/CostModelBuilder';
import Evolution from './pages/Evolution';

import Brief from './pages/Brief';
import Pricing from './pages/Pricing';
import Indexes from './pages/Indexes';
import Dashboard from './pages/Dashboard';
import Suppliers from './pages/Suppliers';
import SupplierPurchases from './pages/SupplierPurchases';
import Products from './pages/Products';
import Admin from './pages/Admin';
import Team from './pages/Team';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';
import { useAuth } from './AuthContext';

export default function App() {
  const { user } = useAuth();

  return (
    <>
      {user && <Navbar />}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/cost-models/new" element={<CostModelBuilder />} />
          <Route path="/cost-models/:costModelId" element={<CostModelBuilder />} />
          <Route path="/cost-models/:costModelId/evolution" element={<Evolution />} />

          <Route path="/cost-models/:costModelId/brief" element={<Brief />} />
          <Route path="/cost-models/:costModelId/pricing" element={<Pricing />} />
          <Route path="/indexes" element={<Indexes />} />
          <Route path="/products" element={<Products />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/suppliers/:supplierId/purchases" element={<SupplierPurchases />} />
          <Route path="/team" element={<Team />} />
          <Route path="/admin" element={<Admin />} />
        </Route>
      </Routes>
      {user && <ImpersonationBar />}
      <Footer />
    </>
  );
}
