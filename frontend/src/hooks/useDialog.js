import {useEffect,useRef} from 'react';
export default function useDialog(onClose,open){
 const ref=useRef(null),close=useRef(onClose);close.current=onClose;
 useEffect(()=>{if(!open)return;const previous=document.activeElement;const root=ref.current;
  const focusable=()=>Array.from(root?.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),[tabindex="0"]')||[]);
  (focusable()[0]||root)?.focus();
  const key=event=>{if(event.key==='Escape'){event.preventDefault();close.current();}if(event.key==='Tab'){const items=focusable();const first=items[0],last=items.at(-1);if(!first){event.preventDefault();return;}if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}};
  root?.addEventListener('keydown',key);return()=>{root?.removeEventListener('keydown',key);if(previous?.isConnected)previous.focus();};
 },[open]);return ref;
}
