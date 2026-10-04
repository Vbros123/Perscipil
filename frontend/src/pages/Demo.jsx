import ResearchTerminal from '../components/dashboard/ResearchTerminal'
import BrandMark from '../components/common/BrandMark'
import { BRAND } from '../lib/brand'
import { Link } from '../router'
export default function Demo(){return <main className="demo-page"><nav className="public-nav"><Link to="/" className="brand"><BrandMark/><strong>{BRAND.name}.</strong></Link><Link to="/signup" className="btn btn-primary">Research real companies</Link></nav><header className="demo-page-heading"><div className="eyebrow">Product demo</div><h1>Your private-company research desk</h1><p>Fictional examples. No live company data or account access.</p></header><ResearchTerminal/></main>}
