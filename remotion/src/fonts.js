import {loadFont as loadAnton} from '@remotion/google-fonts/Anton';
import {loadFont as loadMontserrat} from '@remotion/google-fonts/Montserrat';

export const anton = loadAnton().fontFamily;
export const montserrat = loadMontserrat('normal', {weights: ['700', '800', '900']}).fontFamily;
