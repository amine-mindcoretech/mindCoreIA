//frontend/src/app.js
import { useState } from 'react'
import FileUpload from './components/FileUpload'
import './styles.css'

function App() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleExtraction = async (file) => {
    setLoading(true)
    setError(null)
    setResults(null)
    
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('http://localhost:8000/extract', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Erreur lors de l\'extraction')
      }

      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message || 'Une erreur est survenue')
      console.error('Erreur:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Non trouvé'
    try {
      const [day, month, year] = dateStr.split('/')
      return new Date(`${year}-${month}-${day}`).toLocaleDateString('fr-FR')
    } catch {
      return dateStr
    }
  }

  const formatCurrency = (amount, currency) => {
    if (!amount) return 'Non trouvé'
    try {
      return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: currency || 'EUR'
      }).format(parseFloat(amount.replace(/[^\d.,]/g, '').replace(',', '.')))
    } catch {
      return amount + (currency ? ` ${currency}` : '')
    }
  }

  return (
    <div className="app-container">
      <h1>Extracteur d'informations de commande (PO)</h1>
      <p>Téléchargez un PDF ou une image pour extraire les informations de la commande</p>
      
      <FileUpload 
        onFileUpload={handleExtraction} 
        loading={loading}
        accept=".pdf,.png,.jpg,.jpeg"
      />
      
      {error && (
        <div className="error-message">
          <strong>Erreur:</strong> {error}
        </div>
      )}
      
      {loading && (
        <div className="loading-indicator">
          Traitement en cours... Cette opération peut prendre quelques instants.
        </div>
      )}
      
      {results && (
        <div className="results-container">
          <h2>Résultats d'extraction</h2>
          
          <div className="section">
            <h3>Informations de base</h3>
            <div className="grid-container">
              <div className="info-item"><strong>Numéro de PO:</strong> {results.po_number || 'Non trouvé'}</div>
              <div className="info-item"><strong>Date de PO:</strong> {formatDate(results.po_date)}</div>
              <div className="info-item"><strong>Livré à:</strong> {results.delivered_to || 'Non trouvé'}</div>
              <div className="info-item"><strong>Expédié à:</strong> {results.shipped_to || 'Non trouvé'}</div>
              <div className="info-item"><strong>Code fournisseur:</strong> {results.vendor_code || 'Non trouvé'}</div>
              <div className="info-item"><strong>Réf. fournisseur:</strong> {results.vendor_ref || 'Non trouvé'}</div>
              <div className="info-item"><strong>Expédié par:</strong> {results.ship_via || 'Non trouvé'}</div>
              <div className="info-item"><strong>Émis par:</strong> {results.ordered_by || 'Non trouvé'}</div>
              <div className="info-item"><strong>Termes:</strong> {results.terms || 'Non trouvé'}</div>
            </div>
          </div>
          
          <div className="section">
            <h3>Totaux</h3>
            <div className="grid-container totals">
              <div className="info-item"><strong>Total HT:</strong> {formatCurrency(results.total_without_tax)}</div>
              <div className="info-item"><strong>Taxe:</strong> {formatCurrency(results.tax)}</div>
              <div className="info-item"><strong>TPS:</strong> {formatCurrency(results.tps)}</div>
              <div className="info-item"><strong>TVQ:</strong> {formatCurrency(results.tvq)}</div>
              <div className="info-item"><strong>Total TTC:</strong> {formatCurrency(results.total_with_tax)}</div>
            </div>
          </div>
          
          {results.items && results.items.length > 0 && (
            <div className="section">
              <h3>Articles ({results.items.length})</h3>
              <div className="items-table">
                <table>
                  <thead>
                    <tr>
                      <th>N° pièce</th>
                      <th>Description</th>
                      <th>Quantité</th>
                      <th>Prix unitaire</th>
                      <th>Montant</th>
                      <th>Date livraison</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.items.map((item, index) => (
                      <tr key={index}>
                        <td>{item.part_number || '-'}</td>
                        <td>{item.description || '-'}</td>
                        <td>{item.quantity || '-'}</td>
                        <td>{formatCurrency(item.unit_price)}</td>
                        <td>{formatCurrency(item.amount)}</td>
                        <td>{formatDate(item.ship_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App