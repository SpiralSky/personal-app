import { createContext, useContext } from 'react'

const NotifyErrorCtx = createContext<(msg: string) => void>(() => {})
export const useNotifyError = () => useContext(NotifyErrorCtx)
export default NotifyErrorCtx
