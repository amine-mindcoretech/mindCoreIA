//frontend/src/components/FileUpload.jsx
import { useCallback } from 'react'

const FileUpload = ({ onFileUpload, loading, accept }) => {
  const handleFileChange = useCallback((e) => {
    const file = e.target.files?.[0]
    if (file) {
      onFileUpload(file)
    }
    e.target.value = null // Reset pour permettre le re-téléchargement du même fichier
  }, [onFileUpload])

  return (
    <div className="file-upload-container">
      <label className={`file-upload-label ${loading ? 'disabled' : ''}`}>
        <input 
          type="file" 
          accept={accept}
          onChange={handleFileChange}
          disabled={loading}
        />
        {loading ? 'Traitement en cours...' : 'Sélectionner un fichier (PDF/Image)'}
      </label>
      {!loading && <div className="file-hint">Formats acceptés: PDF, JPG, PNG</div>}
    </div>
  )
}

export default FileUpload