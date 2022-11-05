import styled from '@emotion/styled'

const Contenedor = styled.div`
    font-family: 'Lato', sans-serif;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-top: 30px;   
     
`

const IMG = styled.img`
    display: block;
    width: 120px;
`

const Texto = styled.p`
    font-size: 18px;
    span{
        font-weight: 700;
    }
`

const Precio = styled.p`
    font-size: 24px;
    span{
        font-weight: 700;
    }
`

const Resultado = ({resultado}) => {

const {PRICE, HIGHDAY, LOWDAY, CHANGEPCT24HOUR, IMAGEURL, LASTUPDATE} = resultado;

  return (
    <Contenedor>
        <IMG src={`https://cryptocompare.com/${IMAGEURL}`} alt="imagen Cripto" />
        <div>
            <Precio>El Precio es de: <span>{PRICE}</span></Precio>
            <Texto>El Precio mas alto del dia : <span>{HIGHDAY}</span></Texto>
            <Texto>El Precio mas bajo del dia: <span>{LOWDAY}</span></Texto>
            <Texto>Variacion las ultimas 24H: <span>{CHANGEPCT24HOUR}</span></Texto>
            <Texto> Ultima actualizacion fue: <span>{LASTUPDATE}</span></Texto>
        </div>
    </Contenedor>
  )
}

export default Resultado
