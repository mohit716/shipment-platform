import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth'
import { BookPage } from './pages/Book'
import { LoginPage } from './pages/Login'
import { QuotesPage } from './pages/Quotes'
import { RegisterPage } from './pages/Register'
import { ShipmentDetailPage } from './pages/ShipmentDetail'
import { ShipmentsPage } from './pages/Shipments'
import { Shell } from './Shell'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<Shell />}>
            <Route path="/" element={<ShipmentsPage />} />
            <Route path="/book" element={<BookPage />} />
            <Route path="/shipments/:id" element={<ShipmentDetailPage />} />
            <Route path="/quotes" element={<QuotesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
