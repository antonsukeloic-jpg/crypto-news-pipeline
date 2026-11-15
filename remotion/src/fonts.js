import {loadFont as loadAnton} from '@remotion/google-fonts/Anton';
import {loadFont as loadMontserrat} from '@remotion/google-fonts/Montserrat';

// latin-ext is needed for Lithuanian letters (ą č ę ė į š ų ū ž); harmless for English.
const SUBSETS = ['latin', 'latin-ext'];
export const anton = loadAnton('normal', {weights: ['400'], subsets: SUBSETS}).fontFamily;
export const montserrat = loadMontserrat('normal', {weights: ['700', '800', '900'], subsets: SUBSETS}).fontFamily;

// 5HU editorial look
import {loadFont as loadInstrumentSerif} from '@remotion/google-fonts/InstrumentSerif';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadSpaceMono} from '@remotion/google-fonts/SpaceMono';
loadInstrumentSerif('italic', {weights: ['400'], subsets: SUBSETS});
export const serif = loadInstrumentSerif('normal', {weights: ['400'], subsets: SUBSETS}).fontFamily;
export const inter = loadInter('normal', {weights: ['800', '900'], subsets: SUBSETS}).fontFamily;
export const mono = loadSpaceMono('normal', {weights: ['400'], subsets: SUBSETS}).fontFamily;
