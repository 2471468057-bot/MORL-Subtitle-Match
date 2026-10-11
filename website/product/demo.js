export const DEMO_CUTS = [5, 9, 13, 17, 20, 23];
// Segmentation the sample starts from (as if returned by recognition + AI 断句).
export const RECOGNIZED_CUTS = [5, 9, 17, 23];
export const CUT_BEATS = [.22, .38, .42, .58, .61, .64];
export const cutsAtProgress = (p) => CUT_BEATS.filter(at => p >= at).length;
export const nextDemoCut = (cuts, legal) =>
  DEMO_CUTS.find((i) => !cuts.includes(i) && legal.includes(i));
export const mayDemonstrate = ({
  visible,
  occupied,
  focused,
  reduced,
  suspended,
  hidden,
}) => visible && !occupied && !focused && !reduced && !suspended && !hidden;
