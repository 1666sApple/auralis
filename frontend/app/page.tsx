'use client'

import { useEffect, useRef, useState } from 'react'
import { fabric } from 'fabric'
import {
  Type,
  Image,
  Download,
  Undo2,
  Redo2,
  Square,
  Circle,
  PenTool,
  RotateCw,
  Trash2,
  Save,
  Upload,
  Move,
  Layers,
  ZoomIn,
  ZoomOut,
  PanelRightClose,
  PanelRightOpen,
} from 'lucide-react'

export default function OverlayEditor() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fabricRef = useRef<fabric.Canvas | null>(null)
  const [selectedObject, setSelectedObject] = useState<any>(null)
  const [zoom, setZoom] = useState(1)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)
  const [textColor, setTextColor] = useState('#ffffff')
  const [fillColor, setFillColor] = useState('#3b82f6')
  const [strokeColor, setStrokeColor] = useState('#ffffff')
  const [strokeWidth, setStrokeWidth] = useState(2)
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const backgroundFileRef = useRef<File | null>(null)
  const logoFileRef = useRef<File | null>(null)
  const logoObjectRef = useRef<fabric.Object | null>(null)
  const backgroundObjectRef = useRef<fabric.Object | null>(null)

  useEffect(() => {
    if (!canvasRef.current || fabricRef.current) return

    const canvas = new fabric.Canvas(canvasRef.current, {
      width: 1200,
      height: 800,
      backgroundColor: '#1a1a2e',
      preserveObjectStacking: true,
    })

    canvas.on('selection:created', (e) => setSelectedObject(e.selected?.[0]))
    canvas.on('selection:updated', (e) => setSelectedObject(e.selected?.[0]))
    canvas.on('selection:cleared', () => setSelectedObject(null))
    canvas.on('object:modified', () => saveToHistory())

    fabricRef.current = canvas
    return () => {
      canvas.dispose()
      fabricRef.current = null
    }
  }, [])

  const saveToHistory = () => {
    if (!fabricRef.current) return
    const json = JSON.stringify(fabricRef.current.toJSON())
    setHistory(prev => [...prev.slice(0, historyIndex + 1), json])
    setHistoryIndex(prev => prev + 1)
  }

  const uploadBackground = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !fabricRef.current) return

    // Reset input so the same file can be re-selected
    e.target.value = ''

    backgroundFileRef.current = file

    const reader = new FileReader()
    reader.onload = (event) => {
      fabric.Image.fromURL(event.target?.result as string, (img) => {
        if (!fabricRef.current) return
        
        const canvas = fabricRef.current

        // Remove old background if one exists
        if (backgroundObjectRef.current) {
          canvas.remove(backgroundObjectRef.current)
          backgroundObjectRef.current = null
        }

        const originalWidth = img.width!
        const originalHeight = img.height!
        
        // Scale to fit canvas while preserving original dimensions
        const scale = Math.min(canvas.width! / originalWidth, canvas.height! / originalHeight)
        
        img.scale(scale)
        img.set({
          left: (canvas.width! - img.getScaledWidth()) / 2,
          top: (canvas.height! - img.getScaledHeight()) / 2,
          selectable: true,
          // Store original dimensions for export
          data: { originalWidth, originalHeight }
        })

        canvas.add(img)
        canvas.sendToBack(img)
        backgroundObjectRef.current = img
        canvas.renderAll()
        saveToHistory()
      })
    }
    reader.readAsDataURL(file)
  }

  const uploadLogo = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !fabricRef.current) return

    // Reset input so the same file can be re-selected
    e.target.value = ''

    logoFileRef.current = file

    const reader = new FileReader()
    reader.onload = (event) => {
      fabric.Image.fromURL(event.target?.result as string, (img) => {
        const canvas = fabricRef.current!

        // Remove old logo if one exists
        if (logoObjectRef.current) {
          canvas.remove(logoObjectRef.current)
          logoObjectRef.current = null
        }

        const scale = (canvas.width! * 0.2) / img.width!
        
        img.scale(scale)
        img.set({
          left: canvas.width! - img.getScaledWidth() - 20,
          top: 20
        })

        canvas.add(img)
        canvas.setActiveObject(img)
        canvas.renderAll()
        logoObjectRef.current = img
        saveToHistory()
      })
    }
    reader.readAsDataURL(file)
  }

  const addText = () => {
    if (!fabricRef.current) return
    const text = new fabric.IText('Text', {
      left: 100,
      top: 100,
      fontSize: 40,
      fill: textColor,
      fontFamily: 'Arial'
    })
    fabricRef.current.add(text)
    fabricRef.current.setActiveObject(text)
    fabricRef.current.renderAll()
    saveToHistory()
  }

  const addRect = () => {
    if (!fabricRef.current) return
    const rect = new fabric.Rect({
      left: 100,
      top: 100,
      width: 150,
      height: 100,
      fill: fillColor,
      stroke: strokeColor,
      strokeWidth: strokeWidth
    })
    fabricRef.current.add(rect)
    fabricRef.current.setActiveObject(rect)
    fabricRef.current.renderAll()
    saveToHistory()
  }

  const addCircle = () => {
    if (!fabricRef.current) return
    const circle = new fabric.Circle({
      left: 100,
      top: 100,
      radius: 60,
      fill: fillColor,
      stroke: strokeColor,
      strokeWidth: strokeWidth
    })
    fabricRef.current.add(circle)
    fabricRef.current.setActiveObject(circle)
    fabricRef.current.renderAll()
    saveToHistory()
  }

  const deleteSelected = () => {
    if (!fabricRef.current || !selectedObject) return
    fabricRef.current.remove(selectedObject)
    fabricRef.current.renderAll()
    setSelectedObject(null)
    saveToHistory()
  }

  const bringToFront = () => {
    if (!fabricRef.current || !selectedObject) return
    fabricRef.current.bringToFront(selectedObject)
    fabricRef.current.renderAll()
  }

  const sendToBack = () => {
    if (!fabricRef.current || !selectedObject) return
    fabricRef.current.sendToBack(selectedObject)
    fabricRef.current.renderAll()
  }

  /**
   * Extract logo placement parameters from the fabric canvas relative to the
   * background image, so the backend PIL compositor can reproduce the same layout
   * at full original resolution.
   */
  const getLogoPlacementParams = () => {
    const canvas = fabricRef.current!
    const objects = canvas.getObjects()
    const bgObj = objects.find((obj: any) => obj.type === 'image' && obj.data?.originalWidth) as any
    const logoObj = logoObjectRef.current

    if (!bgObj || !logoObj) return null

    // The background image's position & scale on canvas
    const bgLeft = bgObj.left ?? 0
    const bgTop = bgObj.top ?? 0
    const bgScaleOnCanvas = bgObj.scaleX ?? 1 // uniform scale
    const bgOrigW = bgObj.data.originalWidth as number
    const bgOrigH = bgObj.data.originalHeight as number

    // Ratio from canvas‑pixels → original‑pixels
    const canvasToOrig = 1 / bgScaleOnCanvas

    // Logo dimensions on canvas
    const logoScaleOnCanvas = logoObj.scaleX ?? 1
    const logoW = (logoObj.width ?? 0) * logoScaleOnCanvas
    const logoH = (logoObj.height ?? 0) * logoScaleOnCanvas

    // Logo position relative to the background image (in original pixels)
    const logoLeftOnBg = ((logoObj.left ?? 0) - bgLeft) * canvasToOrig
    const logoTopOnBg = ((logoObj.top ?? 0) - bgTop) * canvasToOrig

    // Logo scale relative to original image width
    const logoScaleRelative = (logoW * canvasToOrig) / bgOrigW

    // Determine closest position preset
    const cx = logoLeftOnBg + (logoW * canvasToOrig) / 2
    const cy = logoTopOnBg + (logoH * canvasToOrig) / 2

    let posH = 'center'
    if (cx < bgOrigW * 0.33) posH = 'left'
    else if (cx > bgOrigW * 0.66) posH = 'right'

    let posV = 'center'
    if (cy < bgOrigH * 0.33) posV = 'top'
    else if (cy > bgOrigH * 0.66) posV = 'bottom'

    const positionName = posV === 'center' && posH === 'center'
      ? 'center'
      : posV === 'center'
        ? `center-${posH}`
        : posH === 'center'
          ? `${posV}-center`
          : `${posV}-${posH}`

    // Compute offset from the preset position (padding=0 to let offset do all the work)
    const presetPositions: Record<string, { x: number; y: number }> = {
      'top-left': { x: 0, y: 0 },
      'top-center': { x: (bgOrigW - logoW * canvasToOrig) / 2, y: 0 },
      'top-right': { x: bgOrigW - logoW * canvasToOrig, y: 0 },
      'center-left': { x: 0, y: (bgOrigH - logoH * canvasToOrig) / 2 },
      'center': { x: (bgOrigW - logoW * canvasToOrig) / 2, y: (bgOrigH - logoH * canvasToOrig) / 2 },
      'center-right': { x: bgOrigW - logoW * canvasToOrig, y: (bgOrigH - logoH * canvasToOrig) / 2 },
      'bottom-left': { x: 0, y: bgOrigH - logoH * canvasToOrig },
      'bottom-center': { x: (bgOrigW - logoW * canvasToOrig) / 2, y: bgOrigH - logoH * canvasToOrig },
      'bottom-right': { x: bgOrigW - logoW * canvasToOrig, y: bgOrigH - logoH * canvasToOrig },
    }

    const preset = presetPositions[positionName] ?? presetPositions['top-right']
    const xOffset = Math.round(logoLeftOnBg - preset.x)
    const yOffset = Math.round(logoTopOnBg - preset.y)

    return {
      position: positionName,
      padding: 0,
      logo_scale: logoScaleRelative,
      rotation: logoObj.angle ?? 0,
      opacity: logoObj.opacity ?? 1,
      x_offset: xOffset,
      y_offset: yOffset,
    }
  }

  const compositeViaBackend = async (): Promise<{ blob: Blob; outputPath: string } | null> => {
    if (!backgroundFileRef.current) {
      alert('Please upload a background image first.')
      return null
    }

    const formData = new FormData()
    formData.append('image', backgroundFileRef.current)

    if (logoFileRef.current && logoObjectRef.current) {
      const params = getLogoPlacementParams()
      formData.append('logo', logoFileRef.current)
      formData.append('position', params?.position ?? 'top-right')
      formData.append('padding', String(params?.padding ?? 0))
      formData.append('logo_scale', String(params?.logo_scale ?? 0.15))
      formData.append('rotation', String(params?.rotation ?? 0))
      formData.append('opacity', String(params?.opacity ?? 1))
      formData.append('x_offset', String(params?.x_offset ?? 0))
      formData.append('y_offset', String(params?.y_offset ?? 0))
    } else {
      // No logo — send empty blob so the backend just saves the image
      formData.append('logo', new Blob(), 'none.png')
      formData.append('position', 'top-right')
      formData.append('padding', '0')
      formData.append('logo_scale', '0.15')
    }

    const response = await fetch('http://localhost:8000/v1/overlay/logo', {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.message || 'Backend compositing failed')
    }

    const result = await response.json()
    const outputPath: string = result.data.output_path

    // Fetch the composed image back from the backend for download
    const imageResponse = await fetch(`http://localhost:8000/files/${outputPath}`)
    if (imageResponse.ok) {
      const blob = await imageResponse.blob()
      return { blob, outputPath }
    }

    return { blob: new Blob(), outputPath }
  }

  const downloadImage = async () => {
    if (!fabricRef.current) return

    try {
      const result = await compositeViaBackend()
      if (!result) return

      // If we got the blob back, download it directly
      if (result.blob.size > 0) {
        const url = URL.createObjectURL(result.blob)
        const link = document.createElement('a')
        link.download = `final_design.png`
        link.href = url
        link.click()
        URL.revokeObjectURL(url)
      } else {
        alert(`Image composed and saved on server at:\n${result.outputPath}\n\n(Direct download not available — file is on the server.)`)
      }
    } catch (error) {
      console.error('Export error:', error)
      alert('Error: ' + (error as Error).message)
    }
  }

  const saveToBackend = async () => {
    if (!fabricRef.current) return

    try {
      const result = await compositeViaBackend()
      if (!result) return
      alert(`Saved to backend!\nOutput: ${result.outputPath}`)
    } catch (error) {
      console.error('Save error:', error)
      alert('Error: ' + (error as Error).message)
    }
  }

  const zoomCanvas = (factor: number) => {
    if (!fabricRef.current) return
    const newZoom = Math.max(0.1, Math.min(5, zoom + factor))
    setZoom(newZoom)
    fabricRef.current.setZoom(newZoom)
    fabricRef.current.renderAll()
  }

  const setPositionPreset = (position: string) => {
    if (!fabricRef.current || !selectedObject) return
    const canvas = fabricRef.current
    const obj = selectedObject
    const w = obj.getScaledWidth()
    const h = obj.getScaledHeight()

    const positions: Record<string, { left: number, top: number }> = {
      'top-left': { left: 20, top: 20 },
      'top-center': { left: (canvas.width! - w) / 2, top: 20 },
      'top-right': { left: canvas.width! - w - 20, top: 20 },
      'center-left': { left: 20, top: (canvas.height! - h) / 2 },
      'center': { left: (canvas.width! - w) / 2, top: (canvas.height! - h) / 2 },
      'center-right': { left: canvas.width! - w - 20, top: (canvas.height! - h) / 2 },
      'bottom-left': { left: 20, top: canvas.height! - h - 20 },
      'bottom-center': { left: (canvas.width! - w) / 2, top: canvas.height! - h - 20 },
      'bottom-right': { left: canvas.width! - w - 20, top: canvas.height! - h - 20 }
    }

    obj.set(positions[position])
    canvas.renderAll()
    saveToHistory()
  }

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      <div className="h-16 bg-slate-800/80 border-b border-slate-700 px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-bold text-lg">Overlay Studio</h1>
            <p className="text-xs text-slate-400">Canvas Editor</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={() => zoomCanvas(-0.1)} className="w-9 h-9 rounded-lg bg-slate-700 hover:bg-slate-600"><ZoomOut className="w-5 h-5 mx-auto" /></button>
          <span className="text-sm w-14 text-center">{Math.round(zoom * 100)}%</span>
          <button onClick={() => zoomCanvas(0.1)} className="w-9 h-9 rounded-lg bg-slate-700 hover:bg-slate-600"><ZoomIn className="w-5 h-5 mx-auto" /></button>

          <div className="w-px h-8 bg-slate-600 mx-2" />

          <button onClick={downloadImage} className="px-4 h-10 rounded-lg bg-slate-700 hover:bg-slate-600 flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export
          </button>
          
          <button onClick={saveToBackend} className="px-4 h-10 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 flex items-center gap-2">
            <Save className="w-4 h-4" />
            Save to Backend
          </button>

          <button onClick={() => setRightPanelOpen(!rightPanelOpen)} className="w-9 h-9 rounded-lg bg-slate-700 hover:bg-slate-600">
            {rightPanelOpen ? <PanelRightClose className="w-5 h-5 mx-auto" /> : <PanelRightOpen className="w-5 h-5 mx-auto" />}
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-16 bg-slate-800/50 border-r border-slate-700 flex flex-col items-center py-4 gap-2">
          <label className="w-11 h-11 rounded-xl hover:bg-slate-700 flex items-center justify-center cursor-pointer">
            <input type="file" accept="image/*" onChange={uploadBackground} className="hidden" />
            <Image className="w-5 h-5" />
          </label>

          <label className="w-11 h-11 rounded-xl hover:bg-blue-600/30 flex items-center justify-center cursor-pointer border border-blue-500/50">
            <input type="file" accept="image/*" onChange={uploadLogo} className="hidden" />
            <Upload className="w-5 h-5 text-blue-400" />
          </label>

          <button onClick={addText} className="w-11 h-11 rounded-xl hover:bg-slate-700 flex items-center justify-center">
            <Type className="w-5 h-5" />
          </button>

          <button onClick={addRect} className="w-11 h-11 rounded-xl hover:bg-slate-700 flex items-center justify-center">
            <Square className="w-5 h-5" />
          </button>

          <button onClick={addCircle} className="w-11 h-11 rounded-xl hover:bg-slate-700 flex items-center justify-center">
            <Circle className="w-5 h-5" />
          </button>

          <div className="w-8 h-px bg-slate-700 my-2" />

          <button onClick={bringToFront} className="w-11 h-11 rounded-xl hover:bg-slate-700 flex items-center justify-center text-xs">↑↑</button>
          <button onClick={sendToBack} className="w-11 h-11 rounded-xl hover:bg-slate-700 flex items-center justify-center text-xs">↓↓</button>
          <button onClick={deleteSelected} className="w-11 h-11 rounded-xl hover:bg-red-500/20 text-red-400 flex items-center justify-center">
            <Trash2 className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto bg-slate-800/50 p-8 flex flex-col items-center justify-center">
          <div className="mb-6 flex items-center gap-4">
            <label className="px-6 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 cursor-pointer flex items-center gap-3 border-2 border-dashed border-slate-600 hover:border-blue-500">
              <Image className="w-5 h-5" />
              <span className="font-medium">Upload Background</span>
              <input type="file" accept="image/*" onChange={uploadBackground} className="hidden" />
            </label>

            <label className="px-6 py-3 rounded-xl bg-blue-600/20 hover:bg-blue-600/30 cursor-pointer flex items-center gap-3 border-2 border-dashed border-blue-500/50">
              <Upload className="w-5 h-5 text-blue-400" />
              <span className="font-medium text-blue-400">Upload Logo</span>
              <input type="file" accept="image/*" onChange={uploadLogo} className="hidden" />
            </label>
          </div>

          <div className="rounded-xl shadow-2xl shadow-black/50 overflow-hidden border border-slate-700">
            <canvas ref={canvasRef} />
          </div>

          <div className="mt-4 text-sm text-slate-400">
            Zoom: {Math.round(zoom * 100)}% | Objects: {fabricRef.current?.getObjects().length || 0}
          </div>
        </div>

        {rightPanelOpen && (
          <div className="w-72 bg-slate-800/50 border-l border-slate-700 p-4 overflow-y-auto">
            <div className="space-y-4">
              <div className="bg-slate-700/50 rounded-xl p-4">
                <label className="text-xs font-medium text-slate-400 block mb-2">Fill Color</label>
                <input type="color" value={fillColor} onChange={(e) => setFillColor(e.target.value)} className="w-full h-10 rounded-lg" />
              </div>

              <div className="bg-slate-700/50 rounded-xl p-4">
                <label className="text-xs font-medium text-slate-400 block mb-2">Text Color</label>
                <input type="color" value={textColor} onChange={(e) => setTextColor(e.target.value)} className="w-full h-10 rounded-lg" />
              </div>

              <div className="bg-slate-700/50 rounded-xl p-4">
                <label className="text-xs font-medium text-slate-400 block mb-2">Stroke Color</label>
                <input type="color" value={strokeColor} onChange={(e) => setStrokeColor(e.target.value)} className="w-full h-10 rounded-lg" />
              </div>

              <div className="bg-slate-700/50 rounded-xl p-4">
                <label className="text-xs font-medium text-slate-400 block mb-2">Stroke Width: {strokeWidth}px</label>
                <input type="range" min="1" max="20" value={strokeWidth} onChange={(e) => setStrokeWidth(parseInt(e.target.value))} className="w-full" />
              </div>

              <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-xl p-4 border border-blue-500/30">
                <label className="text-xs font-medium text-blue-300 block mb-3">Position Presets</label>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    { label: 'TL', pos: 'top-left' },
                    { label: 'TC', pos: 'top-center' },
                    { label: 'TR', pos: 'top-right' },
                    { label: 'ML', pos: 'center-left' },
                    { label: 'C', pos: 'center' },
                    { label: 'MR', pos: 'center-right' },
                    { label: 'BL', pos: 'bottom-left' },
                    { label: 'BC', pos: 'bottom-center' },
                    { label: 'BR', pos: 'bottom-right' },
                  ].map(({ label, pos }) => (
                    <button key={pos} onClick={() => setPositionPreset(pos)} className="w-10 h-10 rounded-lg bg-slate-700 hover:bg-blue-500/40 text-xs font-bold">
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {selectedObject && (
                <div className="bg-slate-700/50 rounded-xl p-4">
                  <label className="text-xs font-medium text-slate-400 block mb-3">Object Scale</label>
                  <input
                    type="range"
                    min="10"
                    max="200"
                    defaultValue="100"
                    onChange={(e) => {
                      const scale = parseInt(e.target.value) / 100
                      selectedObject.scale(scale)
                      fabricRef.current?.renderAll()
                    }}
                    className="w-full"
                  />
                </div>
              )}

              {selectedObject && (
                <div className="bg-slate-700/50 rounded-xl p-4">
                  <label className="text-xs font-medium text-slate-400 block mb-2">Opacity</label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    defaultValue={selectedObject.opacity * 100}
                    onChange={(e) => {
                      selectedObject.set('opacity', parseInt(e.target.value) / 100)
                      fabricRef.current?.renderAll()
                    }}
                    className="w-full"
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}