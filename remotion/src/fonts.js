import {loadFont as loadAnton} from '@remotion/google-fonts/Anton';
import {loadFont as loadMontserrat} from '@remotion/google-fonts/Montserrat';

// latin-ext is needed for Lithuanian letters (ą č ę ė į š ų ū ž); harmless for English.
const SUBSETS = ['latin', 'latin-ext'];
export const anton = loadAnton('normal', {weights: ['400'], subsets: SUBSETS}).fontFamily;
export const montserrat = loadMontserrat('normal', {weights: ['700', '800', '900'], subsets: SUBSETS}).fontFamily;
