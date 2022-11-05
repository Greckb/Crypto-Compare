import styled from '@emotion/styled'
import { useEffect, useState } from 'react'
import { monedas } from '../data/monedas'
import useSelectMonedas from '../hooks/useSelectMonedas'
import Error from './Error'



const InputSubmit = styled.input`
  background-color: #9497FF;
  border: none;
  width: 100%;
  padding: 10px;
  color: #fff;
  font-weight: 700;
  text-transform: uppercase;
  font-size: 20px;
  border-radius: 10px;
  transition: background-color .3s ease;
  margin-top: 30px;

  &:hover{
    background-color: #7A7DFE;
    cursor: pointer;
  }
`

const Formulario = ({setMonedas}) => {

const [criptos, setCriptos] = useState([])
const [error, setError] = useState(false)

const [moneda, SelectMonedas] = useSelectMonedas('Elige tu moneda', monedas)
const [criptomoneda, SelectCriptomoneda] = useSelectMonedas('Elige tu Criptomenda', criptos)

//Cuando el componente del formulario este listo va a llamar a nuestra API
//Pero lo va a ejecutar una sola vez
useEffect(()=>{
    const consultarApi = async () =>{
        const url= "https://min-api.cryptocompare.com/data/top/mktcapfull?limit=10&tsym=USD"

        const respuesta = await fetch(url)
        const resultado = await respuesta.json()

        const arrayCriptos = resultado.Data.map(cripto => {

            const objeto = {
                id: cripto.CoinInfo.Name,
                nombre: cripto.CoinInfo.FullName
            }
            return(objeto)
        })
        setCriptos(arrayCriptos)
    }
    consultarApi();
},[])

const handleSubmit = e =>{
    e.preventDefault()
    
    if([moneda, criptomoneda].includes('') ){
        setError(true)
        return
    }
    setError(false)
    setMonedas({moneda,criptomoneda})
}

  return (
    <>
    {error && <Error>Todos los campos son Obligatorios</Error>}
        <form
            onSubmit={handleSubmit}
        >
            <SelectMonedas/>
            <SelectCriptomoneda/>
            
            <InputSubmit 
                type="submit" 
                value="Cotizar"
            />
        </form>
    </>
  )
}

export default Formulario
